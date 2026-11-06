from datetime import date, datetime, timezone
import re
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ConflictException,
    UnprocessableEntityException,
)
from app.core.security import normalize_phone_local, normalize_patient_name
from app.database.models.profile import Profile, Doctor
from app.database.models.patient import Patient, PatientMerge, AppointmentVitals, WelfareRequest
from app.database.models.appointment import Appointment
from app.database.models.visit import Visit, LabOrder, Service
from app.database.models.finance import InvoiceItem, Payment
from app.schemas.patient import (
    FamilyMember,
    FamilyInput,
    MedicalAlerts,
    PatientSummary,
    PatientFile,
    PatientAppointment,
    PatientFileVisit,
    PatientPayment,
    DuplicateCheckRequest,
    DuplicateCandidate,
    DuplicateCheckResult,
    DuplicateGroup,
    PatientMergeRequest,
    PatientMergeResult,
)
from app.schemas.clinical import Medicine, VisitTest
from app.schemas.finance import MoneySummary, PaymentLogEntry
from app.schemas.welfare import WelfareRequestSchema
from app.services.audit_service import log_audit


def build_alerts(patient: Patient) -> MedicalAlerts:
    return MedicalAlerts(
        allergies=list(patient.allergies or []),
        conditions=list(patient.conditions or []),
        blood_type=patient.blood_type,
    )


async def compute_money_for_appointment(db: AsyncSession, appointment_id: int) -> MoneySummary:
    i_stmt = select(InvoiceItem).where(InvoiceItem.appointment_id == appointment_id)
    i_res = await db.execute(i_stmt)
    items = i_res.scalars().all()

    p_stmt = select(Payment).where(Payment.appointment_id == appointment_id)
    p_res = await db.execute(p_stmt)
    payments = p_res.scalars().all()

    total = {"IQD": 0.0, "USD": 0.0}
    paid = {"IQD": 0.0, "USD": 0.0}

    for item in items:
        curr = item.currency if item.currency in total else "IQD"
        total[curr] += float(item.price)

    for p in payments:
        curr = p.currency if p.currency in paid else "IQD"
        if p.kind == "payment":
            paid[curr] += float(p.amount)
        elif p.kind in ("refund", "reversal"):
            paid[curr] -= float(p.amount)

    balance = {
        "IQD": total["IQD"] - paid["IQD"],
        "USD": total["USD"] - paid["USD"],
    }

    return MoneySummary(total=total, paid=paid, balance=balance)


async def resolve_active_patient(db: AsyncSession, patient_id: int) -> Tuple[Patient, bool]:
    """
    Transparently resolves a patient ID. If patient was soft-merged into another patient,
    traverses the pointer chain to find the unified active primary patient.
    Returns (resolved_patient, was_redirected).
    """
    curr_id = patient_id
    was_redirected = False
    hops = 0
    visited = set()

    while hops < 10:
        if curr_id in visited:
            raise ConflictException(message="Circular merge reference detected", code="circular_merge")
        visited.add(curr_id)

        stmt = select(Patient).where(Patient.id == curr_id)
        res = await db.execute(stmt)
        p = res.scalar_one_or_none()
        if not p:
            raise NotFoundException(message="Patient not found", code="not_found")

        if p.merged_into_patient_id is None:
            return p, was_redirected

        curr_id = p.merged_into_patient_id
        was_redirected = True
        hops += 1

    raise ConflictException(message="Exceeded merge recursion depth limit", code="circular_merge")


async def get_my_family(db: AsyncSession, current_user: Profile) -> List[FamilyMember]:
    stmt = (
        select(Patient)
        .where(Patient.account_id == current_user.id, Patient.merged_into_patient_id.is_(None))
        .order_by(
            (Patient.relation != "self"),
            Patient.id,
        )
    )
    res = await db.execute(stmt)
    patients = res.scalars().all()

    return [
        FamilyMember(
            id=p.id,
            name=p.name,
            relation=p.relation,
            birth_date=str(p.birth_date) if p.birth_date else None,
            phone=p.phone or None,
            alerts=build_alerts(p),
        )
        for p in patients
    ]


async def add_family_member(db: AsyncSession, current_user: Profile, req: FamilyInput):
    b_date = date.fromisoformat(req.birth_date) if req.birth_date else None
    norm_name = normalize_patient_name(req.name)
    raw_phone = req.phone or current_user.phone
    norm_phone = normalize_phone_local(raw_phone)

    # Concurrency check against active duplicates
    dup_stmt = select(Patient).where(
        Patient.normalized_phone == norm_phone,
        Patient.normalized_name == norm_name,
        Patient.merged_into_patient_id.is_(None),
    )
    dup = (await db.execute(dup_stmt)).scalar_one_or_none()
    if dup:
        # If this exact patient already exists under the same user, do nothing or raise
        if dup.account_id == current_user.id:
            return
        # If registered without account, attach to current user
        if dup.account_id is None:
            dup.account_id = current_user.id
            dup.relation = req.relation
            if b_date and not dup.birth_date:
                dup.birth_date = b_date
            await db.commit()
            return

    new_p = Patient(
        name=req.name.strip(),
        phone=raw_phone,
        normalized_name=norm_name,
        normalized_phone=norm_phone,
        account_id=current_user.id,
        relation=req.relation,
        birth_date=b_date,
        allergies=[],
        conditions=[],
    )
    db.add(new_p)
    await log_audit(db, current_user, "family.add", req.name.strip())
    await db.commit()


async def update_family_member(db: AsyncSession, current_user: Profile, member_id: int, req: FamilyInput):
    stmt = select(Patient).where(Patient.id == member_id, Patient.account_id == current_user.id)
    res = await db.execute(stmt)
    member = res.scalar_one_or_none()
    if not member:
        raise NotFoundException(message="Family member not found", code="not_found")
    if member.relation == "self":
        raise ForbiddenException(message="Cannot modify primary account profile through family manager", code="forbidden")

    member.name = req.name.strip()
    member.normalized_name = normalize_patient_name(req.name)
    member.relation = req.relation
    member.birth_date = date.fromisoformat(req.birth_date) if req.birth_date else None
    member.phone = req.phone or ""
    member.normalized_phone = normalize_phone_local(req.phone or "")

    await db.commit()


async def remove_family_member(db: AsyncSession, current_user: Profile, member_id: int):
    stmt = select(Patient).where(Patient.id == member_id, Patient.account_id == current_user.id)
    res = await db.execute(stmt)
    member = res.scalar_one_or_none()
    if not member:
        raise NotFoundException(message="Family member not found", code="not_found")
    if member.relation == "self":
        raise ForbiddenException(message="Cannot remove primary account", code="forbidden")

    today = date.today()
    b_stmt = select(Appointment).where(
        Appointment.patient_id == member_id,
        Appointment.date >= today,
        Appointment.status.in_(["booked", "arrived"]),
    )
    b_res = await db.execute(b_stmt)
    if b_res.first():
        raise ConflictException(message="Cannot remove member with active upcoming appointments", code="member_has_bookings")

    member.account_id = None
    await log_audit(db, current_user, "family.remove", member.name)
    await db.commit()


async def search_patients(db: AsyncSession, query: str) -> List[PatientSummary]:
    # Non-merged patients only
    stmt = select(Patient).where(Patient.merged_into_patient_id.is_(None))
    q = query.strip()
    if q:
        norm_q = normalize_patient_name(q)
        norm_phone = normalize_phone_local(q)
        stmt = stmt.where(or_(
            func.lower(Patient.name).contains(q.lower()),
            Patient.phone.contains(q),
            Patient.normalized_name.contains(norm_q) if norm_q else False,
            Patient.normalized_phone.contains(norm_phone) if norm_phone else False,
        ))

    res = await db.execute(stmt)
    patients = res.scalars().all()

    summary_list = []
    for p in patients:
        a_stmt = select(Appointment).where(Appointment.patient_id == p.id)
        a_res = await db.execute(a_stmt)
        appts = a_res.scalars().all()

        v_stmt = select(Visit).where(Visit.patient_id == p.id)
        v_res = await db.execute(v_stmt)
        visits = v_res.scalars().all()

        no_shows = sum(1 for a in appts if a.status == "no_show")
        visited_dates = [str(a.date) for a in appts if a.status in ("arrived", "in_progress", "done")]
        last_visit = max(visited_dates) if visited_dates else None

        has_account = p.account_id is not None and p.relation == "self"

        summary_list.append(
            PatientSummary(
                id=p.id,
                name=p.name,
                phone=p.phone,
                has_account=has_account,
                relation=p.relation if p.account_id else None,
                appointments=len(appts),
                visits=len(visits),
                no_shows=no_shows,
                last_visit=last_visit,
                merged_into_patient_id=p.merged_into_patient_id,
                is_merged=p.merged_into_patient_id is not None,
            )
        )

    summary_list.sort(key=lambda s: (s.last_visit or "", s.name), reverse=True)
    return summary_list


async def get_patient_file(db: AsyncSession, patient_id: int, current_user: Profile) -> PatientFile:
    # Resolve any merged patient transparently to their primary record
    patient, was_redirected = await resolve_active_patient(db, patient_id)
    target_id = patient.id

    await log_audit(db, current_user, "file.open", f"{patient.name} (ID #{target_id})")
    await db.commit()

    # Query family
    family_members = []
    if patient.account_id:
        f_stmt = select(Patient).where(
            Patient.account_id == patient.account_id,
            Patient.id != patient.id,
            Patient.merged_into_patient_id.is_(None),
        )
        f_res = await db.execute(f_stmt)
        family_members = [
            FamilyMember(
                id=m.id,
                name=m.name,
                relation=m.relation,
                birth_date=str(m.birth_date) if m.birth_date else None,
                phone=m.phone or None,
                alerts=build_alerts(m),
            )
            for m in f_res.scalars().all()
        ]

    # Query appointments (all appointments now point to unified patient)
    a_stmt = select(Appointment, Doctor.name_ar).join(Doctor, Appointment.doctor_id == Doctor.id).where(
        Appointment.patient_id == target_id
    ).order_by(Appointment.date.desc(), Appointment.time.desc())
    a_res = await db.execute(a_stmt)
    appt_rows = a_res.all()

    patient_appts = []
    grand_total = {"IQD": 0.0, "USD": 0.0}
    grand_paid = {"IQD": 0.0, "USD": 0.0}

    for appt, doc_name in appt_rows:
        money = await compute_money_for_appointment(db, appt.id)
        if appt.status not in ("cancelled", "no_show"):
            for curr in ("IQD", "USD"):
                grand_total[curr] += money.total[curr]
                grand_paid[curr] += money.paid[curr]

        patient_appts.append(
            PatientAppointment(
                id=appt.id,
                doctor_name=doc_name,
                date=str(appt.date),
                time=appt.time,
                kind=appt.kind,
                branch=appt.branch,
                status=appt.status,
                emergency=appt.emergency,
                cancel_reason=appt.cancel_reason,
                pay_by=appt.pay_by.isoformat() if appt.pay_by else None,
                money=money,
            )
        )

    # Query visits
    v_stmt = select(Visit, Doctor.name_ar).join(Doctor, Visit.doctor_id == Doctor.id).where(
        Visit.patient_id == target_id
    ).order_by(Visit.created_at.desc())
    v_res = await db.execute(v_stmt)
    visit_rows = v_res.all()

    file_visits = []
    for v, doc_name in visit_rows:
        t_stmt = select(LabOrder, Service).join(Service, LabOrder.service_id == Service.id).where(
            LabOrder.visit_id == v.id
        )
        t_res = await db.execute(t_stmt)
        lab_orders = t_res.all()

        visit_tests = [
            VisitTest(
                id=order.id,
                test=Service(
                    id=svc.id,
                    name=svc.name,
                    name_ar=svc.name_ar,
                    kind=svc.kind,
                    price=float(svc.price),
                    currency=svc.currency,
                    template=svc.template,
                ),
                status=order.status,
                result=order.result if order.status == "confirmed" else None,
            )
            for order, svc in lab_orders
        ]

        medicines = [Medicine(**m) for m in (v.medicines or [])]
        file_visits.append(
            PatientFileVisit(
                id=v.id,
                created_at=v.created_at.isoformat(),
                doctor_name=doc_name,
                diagnosis=v.diagnosis,
                medicines=medicines,
                dispensed=v.dispensed,
                tests=visit_tests,
            )
        )

    # Query payments
    appt_ids = [a.id for a, _ in appt_rows]
    payments_list = []
    if appt_ids:
        p_stmt = select(Payment).where(Payment.appointment_id.in_(appt_ids)).order_by(Payment.at.desc())
        p_res = await db.execute(p_stmt)
        for p in p_res.scalars().all():
            payments_list.append(
                PatientPayment(
                    id=p.id,
                    appointment_id=p.appointment_id,
                    amount=float(p.amount),
                    currency=p.currency,
                    method=p.method,
                    kind=p.kind,
                    at=p.at.isoformat(),
                    by=p.by,
                    reason=p.reason or "",
                )
            )

    grand_money = MoneySummary(
        total=grand_total,
        paid=grand_paid,
        balance={
            "IQD": grand_total["IQD"] - grand_paid["IQD"],
            "USD": grand_total["USD"] - grand_paid["USD"],
        },
    )

    no_shows = sum(1 for a in patient_appts if a.status == "no_show")
    visited_dates = [a.date for a in patient_appts if a.status in ("arrived", "in_progress", "done")]
    summary = PatientSummary(
        id=patient.id,
        name=patient.name,
        phone=patient.phone,
        has_account=patient.account_id is not None and patient.relation == "self",
        relation=patient.relation if patient.account_id else None,
        appointments=len(patient_appts),
        visits=len(file_visits),
        no_shows=no_shows,
        last_visit=max(visited_dates) if visited_dates else None,
        merged_into_patient_id=patient.merged_into_patient_id,
        is_merged=patient.merged_into_patient_id is not None,
    )

    # Welfare request
    from app.services.welfare_service import _welfare_to_schema
    stmt_w = select(WelfareRequest).where(WelfareRequest.patient_id == target_id).order_by(WelfareRequest.submitted_at.desc())
    latest_w = (await db.execute(stmt_w)).scalars().first()
    welfare_schema = _welfare_to_schema(latest_w) if latest_w else None

    # Payment log
    from app.services.payment_service import get_patient_payment_history
    history = await get_patient_payment_history(db, current_user, limit=200, offset=0, patient_id=target_id)
    payment_log = [PaymentLogEntry(**item) for item in history.get("items", [])]

    return PatientFile(
        patient=summary,
        alerts=build_alerts(patient),
        family=family_members,
        appointments=patient_appts,
        visits=file_visits,
        payments=payments_list,
        money=grand_money,
        payment_log=payment_log,
        welfare=welfare_schema,
    )


def calculate_name_similarity(norm_a: str, norm_b: str) -> float:
    """
    Computes token-based Jaccard similarity for Arabic names.
    """
    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return len(intersection) / len(union)


async def check_patient_duplicates(db: AsyncSession, req: DuplicateCheckRequest) -> DuplicateCheckResult:
    """
    Detects potential duplicate candidates for a patient registration or creation request.
    Considers normalized phone, Arabic normalized full name, and birth date.
    Distinguishes exact duplicates from family members sharing the same phone.
    """
    norm_phone = normalize_phone_local(req.phone)
    norm_name = normalize_patient_name(req.name)
    b_date = date.fromisoformat(req.birth_date) if req.birth_date else None

    # Fetch active (non-merged) patients that share phone or normalized name
    stmt = select(Patient).where(
        Patient.merged_into_patient_id.is_(None),
        or_(
            Patient.normalized_phone == norm_phone,
            Patient.phone == req.phone,
            Patient.normalized_name == norm_name,
        ),
    )
    res = await db.execute(stmt)
    potential_matches = res.scalars().all()

    candidates: List[DuplicateCandidate] = []
    has_exact_match = False

    for p in potential_matches:
        p_norm_phone = p.normalized_phone or normalize_phone_local(p.phone)
        p_norm_name = p.normalized_name or normalize_patient_name(p.name)

        is_phone_match = (p_norm_phone == norm_phone)
        is_name_match = (p_norm_name == norm_name)
        is_birth_date_match = (b_date is not None and p.birth_date is not None and p.birth_date == b_date)

        confidence = 0.0
        match_type = "unknown"
        reasons = []

        if is_phone_match and is_name_match:
            confidence = 1.0
            match_type = "exact_match"
            has_exact_match = True
            reasons.append("تطابق كامل في رقم الهاتف والاسم (Exact phone and name match)")
            if is_birth_date_match:
                reasons.append("تطابق في تاريخ الميلاد (Birth date match)")
        elif is_phone_match and not is_name_match:
            similarity = calculate_name_similarity(norm_name, p_norm_name)
            if similarity >= 0.5:
                confidence = 0.85
                match_type = "same_phone_similar_name"
                reasons.append("رقم الهاتف متطابق مع تقارب كبير في الاسم (Same phone with similar name)")
            else:
                confidence = 0.40
                match_type = "shared_phone_family"
                reasons.append("رقم الهاتف مشترك مع اسم مختلف (احتمال فرد من العائلة) (Shared phone, likely family)")
        elif not is_phone_match and is_name_match:
            if is_birth_date_match:
                confidence = 0.85
                match_type = "same_name_birth_date"
                reasons.append("تطابق تام في الاسم وتاريخ الميلاد مع اختلاف رقم الهاتف (Same name and birth date)")
            else:
                confidence = 0.50
                match_type = "same_name"
                reasons.append("تطابق تام في الاسم مع اختلاف رقم الهاتف (Same name, different phone)")

        if confidence > 0.3:
            p_summary = PatientSummary(
                id=p.id,
                name=p.name,
                phone=p.phone,
                has_account=(p.account_id is not None and p.relation == "self"),
                relation=p.relation if p.account_id else None,
                appointments=0,
                visits=0,
                no_shows=0,
                last_visit=None,
                merged_into_patient_id=p.merged_into_patient_id,
                is_merged=False,
            )
            candidates.append(
                DuplicateCandidate(
                    patient=p_summary,
                    confidence=confidence,
                    match_type=match_type,
                    reasons=reasons,
                )
            )

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return DuplicateCheckResult(candidates=candidates, has_exact_match=has_exact_match)


async def list_duplicate_groups(db: AsyncSession) -> List[DuplicateGroup]:
    """
    Lists suspicious duplicate groups across the clinic for Manager/Reception review.
    Groups patients who share the same normalized phone and normalized name,
    or have suspicious clusters.
    """
    # Find phones with multiple records
    stmt = (
        select(Patient.normalized_phone, func.count(Patient.id))
        .where(Patient.merged_into_patient_id.is_(None))
        .group_by(Patient.normalized_phone)
        .having(func.count(Patient.id) > 1)
    )
    res = await db.execute(stmt)
    phone_groups = res.fetchall()

    groups: List[DuplicateGroup] = []
    for norm_phone, count in phone_groups:
        p_stmt = select(Patient).where(
            Patient.normalized_phone == norm_phone,
            Patient.merged_into_patient_id.is_(None),
        ).order_by(Patient.id)
        p_res = await db.execute(p_stmt)
        patients = p_res.scalars().all()

        # Check if any have exact normalized name match
        name_map = {}
        for p in patients:
            p_norm_name = p.normalized_name or normalize_patient_name(p.name)
            name_map.setdefault(p_norm_name, []).append(p)

        for n_name, p_list in name_map.items():
            if len(p_list) > 1:
                summaries = [
                    PatientSummary(
                        id=p.id,
                        name=p.name,
                        phone=p.phone,
                        has_account=(p.account_id is not None and p.relation == "self"),
                        relation=p.relation if p.account_id else None,
                        appointments=0,
                        visits=0,
                        no_shows=0,
                        last_visit=None,
                    )
                    for p in p_list
                ]
                groups.append(
                    DuplicateGroup(
                        group_id=f"exact_phone_name_{norm_phone}_{p_list[0].id}",
                        match_type="exact_phone_and_name",
                        patients=summaries,
                    )
                )

    return groups


async def merge_patients(db: AsyncSession, req: PatientMergeRequest, manager: Profile) -> PatientMergeResult:
    """
    Merges a duplicate source patient record into a primary patient record.
    Preserves all appointments, visits, medical alerts, vitals, lab orders, and financial history.
    Soft-merges the source record without deletion.
    Guaranteed atomic execution with row-level locking.
    Accessible ONLY by Manager role.
    """
    if manager.role != "manager":
        raise ForbiddenException(message="Only clinic managers can perform patient record merges", code="forbidden")

    if req.primary_patient_id == req.source_patient_id:
        raise UnprocessableEntityException(message="Cannot merge a patient into themselves", code="self_merge_not_allowed")

    # Acquire row-level locks on both patient records to prevent concurrent merges
    # We order by ID to prevent deadlocks across concurrent calls
    first_id = min(req.primary_patient_id, req.source_patient_id)
    second_id = max(req.primary_patient_id, req.source_patient_id)

    lock_stmt = select(Patient).where(Patient.id.in_([first_id, second_id])).with_for_update()
    locked_patients_res = await db.execute(lock_stmt)
    locked_patients = {p.id: p for p in locked_patients_res.scalars().all()}

    primary = locked_patients.get(req.primary_patient_id)
    source = locked_patients.get(req.source_patient_id)

    if not primary:
        raise NotFoundException(message=f"Primary patient #{req.primary_patient_id} not found", code="not_found")
    if not source:
        raise NotFoundException(message=f"Source patient #{req.source_patient_id} not found", code="not_found")

    if primary.merged_into_patient_id is not None:
        raise ConflictException(
            message=f"Primary patient #{primary.id} is already merged into patient #{primary.merged_into_patient_id}",
            code="patient_already_merged",
        )
    if source.merged_into_patient_id is not None:
        raise ConflictException(
            message=f"Source patient #{source.id} is already merged into patient #{source.merged_into_patient_id}",
            code="patient_already_merged",
        )

    # 1. Transfer appointments
    appt_stmt = (
        update(Appointment)
        .where(Appointment.patient_id == source.id)
        .values(patient_id=primary.id)
    )
    appt_res = await db.execute(appt_stmt)
    appts_transferred = appt_res.rowcount

    # 2. Transfer vitals
    vitals_stmt = (
        update(AppointmentVitals)
        .where(AppointmentVitals.patient_id == source.id)
        .values(patient_id=primary.id)
    )
    vitals_res = await db.execute(vitals_stmt)
    vitals_transferred = vitals_res.rowcount

    # 3. Transfer clinical visits
    visits_stmt = (
        update(Visit)
        .where(Visit.patient_id == source.id)
        .values(patient_id=primary.id)
    )
    visits_res = await db.execute(visits_stmt)
    visits_transferred = visits_res.rowcount

    # 4. Transfer lab orders
    lab_stmt = (
        update(LabOrder)
        .where(LabOrder.patient_id == source.id)
        .values(patient_id=primary.id)
    )
    lab_res = await db.execute(lab_stmt)
    lab_transferred = lab_res.rowcount

    # 5. Transfer welfare requests
    welfare_stmt = (
        update(WelfareRequest)
        .where(WelfareRequest.patient_id == source.id)
        .values(patient_id=primary.id)
    )
    welfare_res = await db.execute(welfare_stmt)
    welfare_transferred = welfare_res.rowcount

    # 6. Consolidate clinical alerts
    primary_allergies = list(primary.allergies or [])
    source_allergies = list(source.allergies or [])
    combined_allergies = list(dict.fromkeys(primary_allergies + source_allergies))
    primary.allergies = combined_allergies

    primary_conditions = list(primary.conditions or [])
    source_conditions = list(source.conditions or [])
    combined_conditions = list(dict.fromkeys(primary_conditions + source_conditions))
    primary.conditions = combined_conditions

    if not primary.blood_type and source.blood_type:
        primary.blood_type = source.blood_type
    if not primary.birth_date and source.birth_date:
        primary.birth_date = source.birth_date
    if not primary.account_id and source.account_id:
        primary.account_id = source.account_id

    # 7. Soft-merge source patient
    now = datetime.now(timezone.utc)
    source.merged_into_patient_id = primary.id
    source.merged_at = now
    source.merged_by = manager.name
    source.merge_reason = req.reason.strip()

    records_transferred = {
        "appointments": appts_transferred,
        "vitals": vitals_transferred,
        "visits": visits_transferred,
        "lab_orders": lab_transferred,
        "welfare_requests": welfare_transferred,
    }

    # 8. Create immutable patient_merges audit entry
    merge_audit = PatientMerge(
        source_patient_id=source.id,
        target_patient_id=primary.id,
        merged_by_id=manager.id,
        merged_by_name=manager.name,
        merge_reason=req.reason.strip(),
        records_transferred=records_transferred,
        created_at=now,
    )
    db.add(merge_audit)

    # 9. Audit log entry
    await log_audit(
        db,
        manager,
        "patient.merge",
        f"Merged patient #{source.id} ({source.name}) into #{primary.id} ({primary.name}): {req.reason.strip()}",
    )

    await db.commit()

    summary = PatientSummary(
        id=primary.id,
        name=primary.name,
        phone=primary.phone,
        has_account=(primary.account_id is not None and primary.relation == "self"),
        relation=primary.relation if primary.account_id else None,
        appointments=appts_transferred,
        visits=visits_transferred,
        no_shows=0,
        last_visit=None,
        merged_into_patient_id=None,
        is_merged=False,
    )

    return PatientMergeResult(
        primary_patient=summary,
        source_patient_id=source.id,
        records_transferred=records_transferred,
        merged_at=now.isoformat(),
        merged_by=manager.name,
    )
