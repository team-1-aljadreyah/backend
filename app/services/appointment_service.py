from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ConflictException,
    UnprocessableEntityException,
)
from app.database.models.profile import Profile, Doctor
from app.database.models.patient import Patient
from app.database.models.appointment import Appointment
from app.database.models.finance import InvoiceItem, Payment
from app.database.models.governance import ClinicSettings
from app.schemas.appointment import (
    BookRequest,
    BookResult,
    StaffBookRequest,
    StaffBookResult,
    RescheduleRequest,
    MyAppointment,
    StaffAppointment,
    WalkInRequest,
    WalkInResult,
)
from app.schemas.patient import BookingRules
from app.schemas.doctor import DoctorSchema
from app.schemas.finance import MoneySummary
from app.services.audit_service import log_audit
from app.core.idempotency import check_idempotency, save_idempotency_record
from app.core.security import normalize_phone_local, normalize_patient_name, validate_three_part_name
from app.services.patient_service import resolve_active_patient
from app.services.notification_service import notify_patient
from app.services.patient_service import compute_money_for_appointment
from app.services.doctor_service import get_doctor_slots, get_weekday_idx, get_ticket_label, SHIFTS
from app.services.welfare_service import get_welfare_percent, add_welfare_discount
from app.services.payment_service import create_payment_session, clean_expired_unpaid_appointments


async def get_settings(db: AsyncSession) -> ClinicSettings:
    stmt = select(ClinicSettings).where(ClinicSettings.id == 1)
    res = await db.execute(stmt)
    settings = res.scalar_one_or_none()
    if not settings:
        settings = ClinicSettings(id=1)
        db.add(settings)
        await db.commit()
    return settings


async def get_patient_booking_rules(db: AsyncSession, patient_id: int) -> BookingRules:
    stmt = select(func.count(Appointment.id)).where(
        Appointment.patient_id == patient_id,
        Appointment.status == "no_show",
    )
    res = await db.execute(stmt)
    no_shows = res.scalar_one() or 0

    settings = await get_settings(db)
    deposit_required = no_shows >= settings.no_show_limit
    welfare_percent = await get_welfare_percent(db, patient_id)
    return BookingRules(
        no_shows=no_shows,
        deposit_required=deposit_required,
        deposit_amount=float(settings.deposit_amount),
        welfare_percent=welfare_percent,
    )


async def can_change_appointment(db: AsyncSession, appt: Appointment) -> bool:
    if appt.status != "booked":
        return False
    settings = await get_settings(db)
    time_str = appt.time or "00:00"
    appt_dt = datetime.fromisoformat(f"{appt.date}T{time_str}:00")
    hours_left = (appt_dt - datetime.now()).total_seconds() / 3600.0
    return hours_left > settings.cancel_hours


async def issue_ticket_for_appointment(db: AsyncSession, appt: Appointment):
    if appt.ticket:
        return
    stmt = select(func.max(Appointment.ticket)).where(
        Appointment.doctor_id == appt.doctor_id,
        Appointment.date == appt.date,
    )
    res = await db.execute(stmt)
    max_ticket = res.scalar_one() or 0
    appt.ticket = max_ticket + 1


async def get_next_arrival_order(db: AsyncSession, target_date: date) -> int:
    stmt = select(func.max(Appointment.arrival_order)).where(Appointment.date == target_date)
    res = await db.execute(stmt)
    max_order = res.scalar_one() or 0
    return max_order + 1


async def book_appointment(db: AsyncSession, req: BookRequest, user: Profile) -> BookResult:
    # Auto-clean expired unpaid appointments
    await clean_expired_unpaid_appointments(db)

    # Verify ownership
    p_stmt = select(Patient).where(Patient.id == req.patient_id, Patient.account_id == user.id)
    p_res = await db.execute(p_stmt)
    patient = p_res.scalar_one_or_none()
    if not patient:
        raise ForbiddenException(message="Patient does not belong to your account", code="forbidden")

    # Idempotency check with payload hashing
    cached = await check_idempotency(db, req.idempotency_key, "appointment.book", req, user.id)
    if cached:
        return BookResult(**cached[1])

    # Check slot availability
    slots = await get_doctor_slots(db, req.doctor_id, req.date, req.kind)
    slot_match = next((s for s in slots if s.time == req.time), None)
    if not slot_match:
        raise ConflictException(message="Doctor does not work on this date/shift", code="day_off")
    if not slot_match.available:
        raise ConflictException(message="This time slot is already taken", code="slot_taken")

    # Check deposit requirements
    rules = await get_patient_booking_rules(db, req.patient_id)
    if rules.deposit_required and req.pay in ("none", "clinic"):
        raise ConflictException(message="Deposit is required for your account due to past no-shows", code="deposit_required")

    # Lock doctor row to serialize concurrent booking transactions
    d_stmt = select(Doctor).where(Doctor.id == req.doctor_id).with_for_update()
    d_res = await db.execute(d_stmt)
    doctor = d_res.scalar_one_or_none()
    if not doctor:
        raise NotFoundException(message="Doctor not found", code="not_found")

    appt_date = date.fromisoformat(req.date)
    w_idx = get_weekday_idx(appt_date)
    branch = (doctor.days[w_idx] or {}).get("branch", "main") if w_idx < len(doctor.days or []) and doctor.days[w_idx] else "main"

    # Time calculations (Baghdad Asia/Baghdad timezone UTC+3)
    duration = doctor.new_minutes if req.kind == "new" else doctor.followup_minutes
    start_time = datetime.fromisoformat(f"{req.date}T{req.time}:00+03:00")
    end_time = start_time + timedelta(minutes=duration)

    new_appt = Appointment(
        patient_id=req.patient_id,
        doctor_id=req.doctor_id,
        date=appt_date,
        time=req.time,
        start_time=start_time,
        end_time=end_time,
        kind=req.kind,
        branch=branch,
        status="booked",
        emergency=False,
        arrival_order=0,
        cancel_reason=None,
        idempotency_key=req.idempotency_key,
    )
    if rules.deposit_required:
        new_appt.pay_by = datetime.now(timezone.utc) + timedelta(minutes=15)

    db.add(new_appt)
    try:
        await db.flush()
    except (IntegrityError, Exception):
        await db.rollback()
        raise ConflictException(message="This time slot is already taken", code="slot_taken")

    # Add consultation fee item
    fee_item = InvoiceItem(
        appointment_id=new_appt.id,
        label="Visit fee",
        label_ar="رسوم الكشف",
        kind="visit",
        price=doctor.fee,
        currency="IQD",
    )
    db.add(fee_item)
    await db.flush()
    await add_welfare_discount(db, new_appt.id)
    await db.flush()

    payment_session = None
    if req.pay in ("deposit", "full"):
        payment_key = f"{req.idempotency_key}:pay" if req.idempotency_key else None
        payment_session = await create_payment_session(
            db,
            new_appt.id,
            req.return_url or "",
            payment_key,
            user,
            pay_choice=req.pay,
        )

    await log_audit(db, user, "appointment.book", patient.name)
    result = BookResult(appointment_id=new_appt.id, payment=payment_session)
    await save_idempotency_record(db, req.idempotency_key, "appointment.book", req, 200, result.model_dump(), user.id)

    try:
        await db.commit()
    except (IntegrityError, Exception):
        await db.rollback()
        raise ConflictException(message="This time slot is already taken", code="slot_taken")

    return result


async def staff_book_appointment(db: AsyncSession, req: StaffBookRequest, user: Profile) -> StaffBookResult:
    # Check idempotency
    cached = await check_idempotency(db, req.idempotency_key, "appointment.staff_book", req, user.id)
    if cached:
        return StaffBookResult(**cached[1])

    target_patient_id = req.patient_id
    if target_patient_id is None:
        if not req.new_patient:
            raise UnprocessableEntityException(message="New patient details required", code="validation_error")
        norm_phone = normalize_phone_local(req.new_patient.phone)
        norm_name = normalize_patient_name(req.new_patient.name)

        p_stmt = select(Patient).where(
            Patient.normalized_phone == norm_phone,
            Patient.normalized_name == norm_name,
            Patient.merged_into_patient_id.is_(None),
        )
        p_res = await db.execute(p_stmt)
        p = p_res.scalar_one_or_none()
        if not p:
            p = Patient(
                name=req.new_patient.name.strip(),
                phone=req.new_patient.phone,
                normalized_name=norm_name,
                normalized_phone=norm_phone,
                account_id=None,
                relation="self",
                allergies=[],
                conditions=[],
            )
            db.add(p)
            await db.flush()
        target_patient_id = p.id
        patient_name = p.name
    else:
        p, _ = await resolve_active_patient(db, target_patient_id)
        target_patient_id = p.id
        patient_name = p.name

    # Check slot
    slots = await get_doctor_slots(db, req.doctor_id, req.date, req.kind)
    slot_match = next((s for s in slots if s.time == req.time), None)
    if not slot_match or not slot_match.available:
        raise ConflictException(message="Slot not available", code="slot_taken")

    d_stmt = select(Doctor).where(Doctor.id == req.doctor_id).with_for_update()
    d_res = await db.execute(d_stmt)
    doctor = d_res.scalar_one_or_none()
    if not doctor:
        raise NotFoundException(message="Doctor not found", code="not_found")

    appt_date = date.fromisoformat(req.date)
    w_idx = get_weekday_idx(appt_date)
    branch = (doctor.days[w_idx] or {}).get("branch", "main") if w_idx < len(doctor.days or []) and doctor.days[w_idx] else "main"

    duration = doctor.new_minutes if req.kind == "new" else doctor.followup_minutes
    start_time = datetime.fromisoformat(f"{req.date}T{req.time}:00+03:00")
    end_time = start_time + timedelta(minutes=duration)

    new_appt = Appointment(
        patient_id=target_patient_id,
        doctor_id=req.doctor_id,
        date=appt_date,
        time=req.time,
        start_time=start_time,
        end_time=end_time,
        kind=req.kind,
        branch=branch,
        status="booked",
        emergency=False,
        arrival_order=0,
        cancel_reason=None,
        idempotency_key=req.idempotency_key,
    )
    db.add(new_appt)
    try:
        await db.flush()
    except (IntegrityError, Exception):
        await db.rollback()
        raise ConflictException(message="Slot not available", code="slot_taken")

    fee_item = InvoiceItem(
        appointment_id=new_appt.id,
        label="Visit fee",
        label_ar="رسوم الكشف",
        kind="visit",
        price=doctor.fee,
        currency="IQD",
    )
    db.add(fee_item)
    await add_welfare_discount(db, new_appt.id)

    await notify_patient(
        db,
        target_patient_id,
        f"booked:{new_appt.id}",
        "booked",
        {"doctor": doctor.name_ar, "date": req.date, "time": req.time},
    )

    await log_audit(db, user, "appointment.book", patient_name)
    result = StaffBookResult(patient_id=target_patient_id)
    await save_idempotency_record(db, req.idempotency_key, "appointment.staff_book", req, 200, result.model_dump(), user.id)

    try:
        await db.commit()
    except (IntegrityError, Exception):
        await db.rollback()
        raise ConflictException(message="Slot not available", code="slot_taken")

    return result


async def cancel_appointment(db: AsyncSession, appt_id: int, user: Profile):
    stmt = select(Appointment, Patient).join(Patient, Appointment.patient_id == Patient.id).where(
        Appointment.id == appt_id
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise NotFoundException(message="Appointment not found", code="not_found")
    appt, patient = row

    if user.role == "patient" and patient.account_id != user.id:
        raise ForbiddenException(message="Access forbidden", code="forbidden")

    if not await can_change_appointment(db, appt):
        raise ConflictException(message="Appointment is within non-cancellation window", code="too_late")

    appt.status = "cancelled"
    appt.cancel_reason = "patient"

    # Refund online payments
    p_stmt = select(Payment).where(
        Payment.appointment_id == appt.id,
        Payment.method == "online",
        Payment.kind == "payment",
    )
    p_res = await db.execute(p_stmt)
    for p in p_res.scalars().all():
        chk = select(Payment).where(Payment.ref_id == p.id)
        if not (await db.execute(chk)).scalar_one_or_none():
            refund_p = Payment(
                appointment_id=appt.id,
                amount=p.amount,
                currency=p.currency,
                method="online",
                kind="refund",
                by=user.name,
                reason="patient_cancel",
                ref_id=p.id,
                key=f"refund:{p.id}",
            )
            db.add(refund_p)

    await log_audit(db, user, "appointment.cancel", patient.name)
    await db.commit()


async def reschedule_appointment(db: AsyncSession, appt_id: int, req: RescheduleRequest, user: Profile):
    stmt = select(Appointment, Patient).join(Patient, Appointment.patient_id == Patient.id).where(
        Appointment.id == appt_id
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise NotFoundException(message="Appointment not found", code="not_found")
    appt, patient = row

    if user.role == "patient" and patient.account_id != user.id:
        raise ForbiddenException(message="Access forbidden", code="forbidden")

    if not await can_change_appointment(db, appt):
        raise ConflictException(message="Appointment is within non-changeable window", code="too_late")

    slots = await get_doctor_slots(db, appt.doctor_id, req.date, appt.kind, ignore_appointment_id=appt.id)
    slot_match = next((s for s in slots if s.time == req.time), None)
    if not slot_match or not slot_match.available:
        raise ConflictException(message="Slot not available", code="slot_taken")

    d_stmt = select(Doctor).where(Doctor.id == appt.doctor_id).with_for_update()
    doctor = (await db.execute(d_stmt)).scalar_one()

    new_date = date.fromisoformat(req.date)
    w_idx = get_weekday_idx(new_date)
    branch = (doctor.days[w_idx] or {}).get("branch", "main") if w_idx < len(doctor.days or []) and doctor.days[w_idx] else "main"

    duration = doctor.new_minutes if appt.kind == "new" else doctor.followup_minutes
    start_time = datetime.fromisoformat(f"{req.date}T{req.time}:00+03:00")
    end_time = start_time + timedelta(minutes=duration)

    appt.date = new_date
    appt.time = req.time
    appt.start_time = start_time
    appt.end_time = end_time
    appt.branch = branch

    await log_audit(db, user, "appointment.reschedule", patient.name)
    try:
        await db.commit()
    except (IntegrityError, Exception):
        await db.rollback()
        raise ConflictException(message="Slot not available", code="slot_taken")


async def check_in_appointment(db: AsyncSession, appt_id: int, emergency: bool, user: Profile, idempotency_key: Optional[str] = None):
    if idempotency_key:
        cached = await check_idempotency(db, idempotency_key, "appointment.check_in", {"appt_id": appt_id, "emergency": emergency}, user.id)
        if cached:
            return

    stmt = select(Appointment, Patient).join(Patient, Appointment.patient_id == Patient.id).where(
        Appointment.id == appt_id
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise NotFoundException(message="Appointment not found", code="not_found")
    appt, patient = row

    if appt.status != "arrived":
        arrival_order = await get_next_arrival_order(db, appt.date)
        appt.status = "arrived"
        appt.emergency = emergency
        appt.arrival_order = arrival_order
        await issue_ticket_for_appointment(db, appt)

    await log_audit(db, user, "appointment.checkin", patient.name)
    if idempotency_key:
        await save_idempotency_record(db, idempotency_key, "appointment.check_in", {"appt_id": appt_id, "emergency": emergency}, 200, {"success": True}, user.id)
    await db.commit()


async def add_walk_in(db: AsyncSession, req: WalkInRequest, user: Profile) -> WalkInResult:
    # Check idempotency
    cached = await check_idempotency(db, req.idempotency_key, "appointment.walk_in", req, user.id)
    if cached:
        return WalkInResult(**cached[1])

    validate_three_part_name(req.name)

    norm_phone = normalize_phone_local(req.phone)
    norm_name = normalize_patient_name(req.name)

    # Check if exact patient exists (same normalized phone and name)
    p_stmt = select(Patient).where(
        Patient.normalized_phone == norm_phone,
        Patient.normalized_name == norm_name,
        Patient.merged_into_patient_id.is_(None),
    )
    p_res = await db.execute(p_stmt)
    existing_patient = p_res.scalar_one_or_none()

    if existing_patient:
        patient = existing_patient
        duplicate = True
    else:
        patient = Patient(
            name=req.name.strip(),
            phone=req.phone,
            normalized_name=norm_name,
            normalized_phone=norm_phone,
            account_id=None,
            relation="self",
            allergies=[],
            conditions=[],
        )
        db.add(patient)
        await db.flush()
        duplicate = False

    d_stmt = select(Doctor).where(Doctor.id == req.doctor_id)
    doctor = (await db.execute(d_stmt)).scalar_one_or_none()
    if not doctor:
        raise NotFoundException(message="Doctor not found", code="not_found")

    today = date.today()
    w_idx = get_weekday_idx(today)
    branch = (doctor.days[w_idx] or {}).get("branch", "main") if w_idx < len(doctor.days or []) and doctor.days[w_idx] else "main"

    arrival_order = await get_next_arrival_order(db, today)
    walk_in_appt = Appointment(
        patient_id=patient.id,
        doctor_id=req.doctor_id,
        date=today,
        time="",
        start_time=None,
        end_time=None,
        kind="new",
        branch=branch,
        status="arrived",
        emergency=req.emergency,
        arrival_order=arrival_order,
        cancel_reason=None,
        idempotency_key=req.idempotency_key,
    )
    db.add(walk_in_appt)
    await db.flush()

    await issue_ticket_for_appointment(db, walk_in_appt)

    # Fee line item
    fee_item = InvoiceItem(
        appointment_id=walk_in_appt.id,
        label="Visit fee",
        label_ar="رسوم الكشف",
        kind="visit",
        price=doctor.fee,
        currency="IQD",
    )
    db.add(fee_item)
    await add_welfare_discount(db, walk_in_appt.id)

    await log_audit(db, user, "walkin.add", patient.name)
    res = WalkInResult(duplicate=duplicate)
    await save_idempotency_record(db, req.idempotency_key, "appointment.walk_in", req, 200, res.model_dump(), user.id)
    await db.commit()
    return res


async def mark_no_show(db: AsyncSession, appt_id: int, user: Profile):
    stmt = select(Appointment, Patient).join(Patient, Appointment.patient_id == Patient.id).where(
        Appointment.id == appt_id
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise NotFoundException(message="Appointment not found", code="not_found")
    appt, patient = row

    if appt.status != "booked":
        raise ConflictException(message="Appointment is not booked", code="not_booked")

    time_str = appt.time or "00:00"
    appt_dt = datetime.fromisoformat(f"{appt.date}T{time_str}:00")
    if appt_dt > datetime.now():
        raise ConflictException(message="Appointment start time has not yet passed", code="not_started")

    appt.status = "no_show"
    await log_audit(db, user, "appointment.no_show", patient.name)
    await db.commit()


async def list_booked_today(db: AsyncSession) -> List[StaffAppointment]:
    today = date.today()
    stmt = (
        select(Appointment, Patient.name, Patient.id)
        .join(Patient, Appointment.patient_id == Patient.id)
        .where(Appointment.date == today, Appointment.status == "booked")
        .order_by(Appointment.time.asc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    # Query all doctor ids for ticket labeling
    d_res = await db.execute(select(Doctor.id).order_by(Doctor.id))
    all_doc_ids = list(d_res.scalars().all())

    result = []
    for appt, patient_name, patient_id in rows:
        ticket_lbl = get_ticket_label(appt.doctor_id, all_doc_ids, appt.ticket)
        # Check vitals
        v_stmt = select(Appointment.id).where(Appointment.id == appt.id, Appointment.vitals.has())
        has_v = bool((await db.execute(v_stmt)).scalar_one_or_none())

        result.append(
            StaffAppointment(
                id=appt.id,
                patient_id=patient_id,
                patient_name=patient_name,
                doctor_id=appt.doctor_id,
                date=str(appt.date),
                time=appt.time,
                kind=appt.kind,
                branch=appt.branch,
                status=appt.status,
                emergency=appt.emergency,
                ticket=ticket_lbl,
                has_vitals=has_v,
            )
        )
    return result


async def get_doctor_queue(db: AsyncSession, doctor_id: int, user: Profile) -> List[StaffAppointment]:
    if user.role == "doctor" and user.doctor_id != doctor_id:
        raise ForbiddenException(message="Doctors may only access their own queue", code="forbidden")

    today = date.today()
    # Queue ordering rule:
    # 0: in_progress
    # 1: emergency
    # 2: timed appointments (by time)
    # 3: walk-ins (by arrival order)
    stmt = (
        select(Appointment, Patient.name, Patient.id)
        .join(Patient, Appointment.patient_id == Patient.id)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.date == today,
            Appointment.status.in_(["arrived", "in_progress"]),
        )
    )
    res = await db.execute(stmt)
    rows = res.all()

    d_res = await db.execute(select(Doctor.id).order_by(Doctor.id))
    all_doc_ids = list(d_res.scalars().all())

    def sort_key(item):
        appt, _, _ = item
        if appt.status == "in_progress":
            rank = 0
        elif appt.emergency:
            rank = 1
        elif appt.time:
            rank = 2
        else:
            rank = 3
        sub = appt.time if rank == 2 else f"{appt.arrival_order:06d}"
        return (rank, sub)

    sorted_rows = sorted(rows, key=sort_key)

    result = []
    for appt, patient_name, patient_id in sorted_rows:
        ticket_lbl = get_ticket_label(appt.doctor_id, all_doc_ids, appt.ticket)
        v_stmt = select(Appointment.id).where(Appointment.id == appt.id, Appointment.vitals.has())
        has_v = bool((await db.execute(v_stmt)).scalar_one_or_none())

        result.append(
            StaffAppointment(
                id=appt.id,
                patient_id=patient_id,
                patient_name=patient_name,
                doctor_id=appt.doctor_id,
                date=str(appt.date),
                time=appt.time,
                kind=appt.kind,
                branch=appt.branch,
                status=appt.status,
                emergency=appt.emergency,
                ticket=ticket_lbl,
                has_vitals=has_v,
            )
        )
    return result


async def get_my_appointments(db: AsyncSession, user: Profile) -> List[MyAppointment]:
    await clean_expired_unpaid_appointments(db)
    today = date.today()
    # Get all patients owned by user account
    p_stmt = select(Patient.id).where(Patient.account_id == user.id)
    patient_ids = list((await db.execute(p_stmt)).scalars().all())

    if not patient_ids:
        return []

    stmt = (
        select(Appointment, Patient.name, Doctor)
        .join(Patient, Appointment.patient_id == Patient.id)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .where(
            Appointment.patient_id.in_(patient_ids),
            Appointment.date >= today,
            or_(
                Appointment.status.in_(["booked", "arrived", "in_progress"]),
                Appointment.cancel_reason == "doctor_absent",
            ),
        )
        .order_by(Appointment.date.asc(), Appointment.time.asc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    d_res = await db.execute(select(Doctor.id).order_by(Doctor.id))
    all_doc_ids = list(d_res.scalars().all())

    result = []
    for appt, patient_name, doc in rows:
        ticket_lbl = get_ticket_label(appt.doctor_id, all_doc_ids, appt.ticket)
        money = await compute_money_for_appointment(db, appt.id)
        can_chg = await can_change_appointment(db, appt)
        late_mins = doc.late_minutes if doc.late_date == appt.date and appt.status != "cancelled" else 0

        # Ahead position in queue
        ahead = None
        if appt.status in ("arrived", "in_progress") and appt.date == today:
            q_stmt = select(Appointment.id).where(
                Appointment.doctor_id == appt.doctor_id,
                Appointment.date == today,
                Appointment.status.in_(["arrived", "in_progress"]),
            )
            # Find index
            q_res = await db.execute(q_stmt)
            q_ids = list(q_res.scalars().all())
            if appt.id in q_ids:
                ahead = q_ids.index(appt.id)

        result.append(
            MyAppointment(
                id=appt.id,
                patient_name=patient_name,
                doctor=DoctorSchema(
                    id=doc.id,
                    name=doc.name,
                    name_ar=doc.name_ar,
                    specialty=doc.specialty,
                    specialty_ar=doc.specialty_ar,
                    fee=float(doc.fee),
                    new_minutes=doc.new_minutes,
                    followup_minutes=doc.followup_minutes,
                ),
                date=str(appt.date),
                time=appt.time,
                kind=appt.kind,
                branch=appt.branch,
                status=appt.status,
                ahead=ahead,
                can_change=can_chg,
                cancel_reason=appt.cancel_reason,
                late_minutes=late_mins,
                ticket=ticket_lbl,
                pay_by=appt.pay_by.isoformat() if appt.pay_by else None,
                money=money,
            )
        )
    return result


async def get_upcoming_appointments(
    db: AsyncSession,
    days: int,
    doctor_id: Optional[int],
    include_today: bool,
    user: Profile,
) -> List[StaffAppointment]:
    await clean_expired_unpaid_appointments(db)
    today = date.today()
    from_date = today if include_today else today + timedelta(days=1)
    to_date = today + timedelta(days=min(max(days, 1), 60))

    target_doctor_id = user.doctor_id if user.role == "doctor" else doctor_id

    stmt = (
        select(Appointment, Patient.name, Patient.id)
        .join(Patient, Appointment.patient_id == Patient.id)
        .where(
            Appointment.status == "booked",
            Appointment.date >= from_date,
            Appointment.date <= to_date,
        )
    )
    if target_doctor_id:
        stmt = stmt.where(Appointment.doctor_id == target_doctor_id)

    stmt = stmt.order_by(Appointment.date.asc(), Appointment.time.asc())
    rows = (await db.execute(stmt)).all()

    d_res = await db.execute(select(Doctor.id).order_by(Doctor.id))
    all_doc_ids = list(d_res.scalars().all())

    result = []
    for appt, patient_name, patient_id in rows:
        ticket_lbl = get_ticket_label(appt.doctor_id, all_doc_ids, appt.ticket)
        v_stmt = select(Appointment.id).where(Appointment.id == appt.id, Appointment.vitals.has())
        has_v = bool((await db.execute(v_stmt)).scalar_one_or_none())

        result.append(
            StaffAppointment(
                id=appt.id,
                patient_id=patient_id,
                patient_name=patient_name,
                doctor_id=appt.doctor_id,
                date=str(appt.date),
                time=appt.time,
                kind=appt.kind,
                branch=appt.branch,
                status=appt.status,
                emergency=appt.emergency,
                ticket=ticket_lbl,
                has_vitals=has_v,
                pay_by=appt.pay_by.isoformat() if appt.pay_by else None,
            )
        )
    return result
