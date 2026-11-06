from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ConflictException,
    UnprocessableEntityException,
)
from app.database.models.profile import Profile, Doctor
from app.database.models.patient import Patient, AppointmentVitals
from app.database.models.appointment import Appointment
from app.database.models.visit import Visit, LabOrder, Service
from app.database.models.finance import InvoiceItem
from app.schemas.clinical import (
    Vitals,
    VitalsRecord,
    Medicine,
    VisitRating,
    RateVisitRequest,
    MyVisit,
    DoctorVisit,
    VisitTest,
    FollowUp,
    FinishVisitRequest,
    FinishVisitResult,
)
from app.schemas.patient import MedicalAlerts
from app.schemas.doctor import DoctorSchema
from app.schemas.service import ServiceSchema
from app.services.audit_service import log_audit
from app.services.notification_service import notify_patient
from app.services.doctor_service import get_ticket_label


async def require_doctor_sees_patient(db: AsyncSession, doctor_user: Profile, patient_id: int):
    if doctor_user.role == "manager":
        return
    if doctor_user.role == "doctor":
        if not doctor_user.doctor_id:
            raise ForbiddenException(message="Doctor profile missing doctor_id", code="forbidden")
        from sqlalchemy import func
        doc_stmt = select(func.count(Appointment.id)).where(
            Appointment.patient_id == patient_id,
            Appointment.doctor_id == doctor_user.doctor_id,
        )
        has_appt = (await db.execute(doc_stmt)).scalar() or 0
        if has_appt == 0:
            raise ForbiddenException(
                message="Doctor can only access records of patients who have or had an appointment with them",
                code="forbidden",
            )
        return
    if doctor_user.role == "reception":
        return
    raise ForbiddenException(message="Doctor does not have a clinical relationship with this patient", code="forbidden")


async def start_visit(db: AsyncSession, appt_id: int, user: Profile):
    stmt = select(Appointment).where(Appointment.id == appt_id)
    appt = (await db.execute(stmt)).scalar_one_or_none()
    if not appt:
        raise NotFoundException(message="Appointment not found", code="not_found")

    if user.role == "doctor" and appt.doctor_id != user.doctor_id:
        raise ForbiddenException(message="Doctors may only start consultations for their own patients", code="forbidden")

    appt.status = "in_progress"
    appt.called_at = datetime.now(timezone.utc)
    await db.commit()


async def finish_visit(db: AsyncSession, appt_id: int, req: FinishVisitRequest, user: Profile) -> FinishVisitResult:
    stmt = select(Appointment, Patient).join(Patient, Appointment.patient_id == Patient.id).where(
        Appointment.id == appt_id
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise NotFoundException(message="Appointment not found", code="not_found")
    appt, patient = row

    if user.role == "doctor" and appt.doctor_id != user.doctor_id:
        raise ForbiddenException(message="Doctors may only finish their own consultations", code="forbidden")

    appt.status = "done"

    follow_up_date = None
    if req.follow_up_days:
        follow_up_date = date.today() + timedelta(days=req.follow_up_days)

    new_visit = Visit(
        created_at=datetime.now(timezone.utc),
        patient_id=appt.patient_id,
        doctor_id=appt.doctor_id,
        appointment_id=appt.id,
        diagnosis=req.diagnosis.strip(),
        internal_note=req.internal_note.strip(),
        medicines=[m.model_dump() for m in req.medicines],
        dispensed=len(req.medicines) == 0,
        follow_up_on=follow_up_date,
    )
    db.add(new_visit)
    await db.flush()

    # Add invoice items for services, procedures and tests
    all_service_ids = list(set(req.test_ids + req.procedure_ids))
    if all_service_ids:
        svc_stmt = select(Service).where(Service.id.in_(all_service_ids))
        services = (await db.execute(svc_stmt)).scalars().all()
        for svc in services:
            item = InvoiceItem(
                appointment_id=appt.id,
                label=svc.name,
                label_ar=svc.name_ar,
                kind=svc.kind,
                price=svc.price,
                currency=svc.currency,
            )
            db.add(item)

    # Create lab orders for test_ids
    for test_id in req.test_ids:
        order = LabOrder(
            visit_id=new_visit.id,
            patient_id=appt.patient_id,
            doctor_id=appt.doctor_id,
            service_id=test_id,
            status="requested",
            result=None,
            history=[],
            requested_at=datetime.now(timezone.utc),
            confirmed_at=None,
        )
        db.add(order)

    # Doctor name for notifications
    d_stmt = select(Doctor).where(Doctor.id == appt.doctor_id)
    doctor = (await db.execute(d_stmt)).scalar_one()

    await notify_patient(
        db,
        appt.patient_id,
        f"rate:{appt.id}",
        "rate_visit",
        {"doctor": doctor.name_ar},
    )

    if follow_up_date:
        await notify_patient(
            db,
            appt.patient_id,
            f"followup:{new_visit.id}",
            "follow_up",
            {"doctor": doctor.name_ar, "date": str(follow_up_date)},
        )

    # Call next patient automatically
    q_stmt = select(Appointment).where(
        Appointment.doctor_id == appt.doctor_id,
        Appointment.date == date.today(),
        Appointment.status == "arrived",
    ).order_by(
        Appointment.emergency.desc(),
        Appointment.time.asc(),
        Appointment.arrival_order.asc(),
    )
    next_appt = (await db.execute(q_stmt)).scalars().first()

    next_ticket_str = None
    if next_appt:
        next_appt.status = "in_progress"
        next_appt.called_at = datetime.now(timezone.utc)
        d_ids = list((await db.execute(select(Doctor.id).order_by(Doctor.id))).scalars().all())
        next_ticket_str = get_ticket_label(next_appt.doctor_id, d_ids, next_appt.ticket)

    await log_audit(db, user, "visit.finish", patient.name)
    await db.commit()

    return FinishVisitResult(next_ticket=next_ticket_str)


async def save_vitals(db: AsyncSession, appt_id: int, req: Vitals, user: Profile) -> VitalsRecord:
    stmt = select(Appointment, Patient).join(Patient, Appointment.patient_id == Patient.id).where(
        Appointment.id == appt_id
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise NotFoundException(message="Appointment not found", code="not_found")
    appt, patient = row

    today = date.today()
    if appt.date != today or appt.status not in ("arrived", "in_progress"):
        raise ConflictException(message="Patient is not currently present at clinic", code="not_here")

    if user.role == "doctor" and appt.doctor_id != user.doctor_id:
        raise ForbiddenException(message="Access denied", code="forbidden")

    v_stmt = select(AppointmentVitals).where(AppointmentVitals.appointment_id == appt_id)
    vitals = (await db.execute(v_stmt)).scalar_one_or_none()

    now_utc = datetime.now(timezone.utc)
    if not vitals:
        vitals = AppointmentVitals(
            appointment_id=appt_id,
            patient_id=appt.patient_id,
            systolic=req.systolic,
            diastolic=req.diastolic,
            temperature=req.temperature,
            pulse=req.pulse,
            spo2=req.spo2,
            weight=req.weight,
            height=req.height,
            at=now_utc,
            by=user.name,
        )
        db.add(vitals)
    else:
        vitals.systolic = req.systolic
        vitals.diastolic = req.diastolic
        vitals.temperature = req.temperature
        vitals.pulse = req.pulse
        vitals.spo2 = req.spo2
        vitals.weight = req.weight
        vitals.height = req.height
        vitals.at = now_utc
        vitals.by = user.name

    await log_audit(db, user, "vitals.save", patient.name)
    await db.commit()

    return VitalsRecord(
        appointment_id=appt_id,
        systolic=float(vitals.systolic) if vitals.systolic else None,
        diastolic=float(vitals.diastolic) if vitals.diastolic else None,
        temperature=float(vitals.temperature) if vitals.temperature else None,
        pulse=vitals.pulse,
        spo2=float(vitals.spo2) if vitals.spo2 else None,
        weight=float(vitals.weight) if vitals.weight else None,
        height=float(vitals.height) if vitals.height else None,
        at=vitals.at.isoformat(),
        by=vitals.by,
    )


async def get_patient_vitals(db: AsyncSession, patient_id: int, user: Profile) -> List[VitalsRecord]:
    if user.role == "doctor":
        await require_doctor_sees_patient(db, user, patient_id)

    stmt = select(AppointmentVitals).where(AppointmentVitals.patient_id == patient_id).order_by(
        AppointmentVitals.at.desc()
    )
    records = (await db.execute(stmt)).scalars().all()

    return [
        VitalsRecord(
            appointment_id=v.appointment_id,
            systolic=float(v.systolic) if v.systolic else None,
            diastolic=float(v.diastolic) if v.diastolic else None,
            temperature=float(v.temperature) if v.temperature else None,
            pulse=v.pulse,
            spo2=float(v.spo2) if v.spo2 else None,
            weight=float(v.weight) if v.weight else None,
            height=float(v.height) if v.height else None,
            at=v.at.isoformat(),
            by=v.by,
        )
        for v in records
    ]


async def get_patient_alerts(db: AsyncSession, patient_id: int, user: Profile) -> MedicalAlerts:
    if user.role == "doctor":
        await require_doctor_sees_patient(db, user, patient_id)

    stmt = select(Patient).where(Patient.id == patient_id)
    p = (await db.execute(stmt)).scalar_one_or_none()
    if not p:
        raise NotFoundException(message="Patient not found", code="not_found")

    return MedicalAlerts(
        allergies=list(p.allergies or []),
        conditions=list(p.conditions or []),
        blood_type=p.blood_type,
    )


async def update_patient_alerts(db: AsyncSession, patient_id: int, req: MedicalAlerts, user: Profile) -> MedicalAlerts:
    await require_doctor_sees_patient(db, user, patient_id)

    stmt = select(Patient).where(Patient.id == patient_id)
    p = (await db.execute(stmt)).scalar_one_or_none()
    if not p:
        raise NotFoundException(message="Patient not found", code="not_found")

    # Clean & deduplicate case-insensitively
    clean_allergies = []
    seen_a = set()
    for a in req.allergies:
        cleaned = a.strip()
        if cleaned and cleaned.lower() not in seen_a:
            seen_a.add(cleaned.lower())
            clean_allergies.append(cleaned)

    clean_conditions = []
    seen_c = set()
    for c in req.conditions:
        cleaned = c.strip()
        if cleaned and cleaned.lower() not in seen_c:
            seen_c.add(cleaned.lower())
            clean_conditions.append(cleaned)

    p.allergies = clean_allergies
    p.conditions = clean_conditions
    p.blood_type = req.blood_type

    await log_audit(db, user, "alerts.update", p.name)
    await db.commit()

    return MedicalAlerts(
        allergies=clean_allergies,
        conditions=clean_conditions,
        blood_type=p.blood_type,
    )


async def get_patient_history(db: AsyncSession, patient_id: int, user: Profile) -> List[DoctorVisit]:
    await require_doctor_sees_patient(db, user, patient_id)

    p_stmt = select(Patient).where(Patient.id == patient_id)
    patient = (await db.execute(p_stmt)).scalar_one_or_none()
    if not patient:
        raise NotFoundException(message="Patient not found", code="not_found")

    await log_audit(db, user, "file.open", patient.name)
    await db.commit()

    v_stmt = select(Visit, Doctor).join(Doctor, Visit.doctor_id == Doctor.id).where(
        Visit.patient_id == patient_id
    ).order_by(Visit.created_at.desc())
    rows = (await db.execute(v_stmt)).all()

    doctor_visits = []
    for v, doc in rows:
        t_stmt = select(LabOrder, Service).join(Service, LabOrder.service_id == Service.id).where(
            LabOrder.visit_id == v.id
        )
        orders = (await db.execute(t_stmt)).all()

        visit_tests = [
            VisitTest(
                id=o.id,
                test=ServiceSchema(
                    id=s.id,
                    name=s.name,
                    name_ar=s.name_ar,
                    kind=s.kind,
                    price=float(s.price),
                    currency=s.currency,
                    template=s.template,
                ),
                status=o.status,
                result=o.result if o.status == "confirmed" else None,
            )
            for o, s in orders
        ]

        doctor_visits.append(
            DoctorVisit(
                id=v.id,
                created_at=v.created_at.isoformat(),
                patient_name=patient.name,
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
                diagnosis=v.diagnosis,
                internal_note=v.internal_note,
                medicines=[Medicine(**m) for m in (v.medicines or [])],
                tests=visit_tests,
                follow_up_on=str(v.follow_up_on) if v.follow_up_on else None,
            )
        )
    return doctor_visits


async def get_my_visits(db: AsyncSession, user: Profile) -> List[MyVisit]:
    p_stmt = select(Patient.id).where(Patient.account_id == user.id)
    patient_ids = list((await db.execute(p_stmt)).scalars().all())
    if not patient_ids:
        return []

    stmt = select(Visit, Patient.name, Doctor).join(
        Patient, Visit.patient_id == Patient.id
    ).join(
        Doctor, Visit.doctor_id == Doctor.id
    ).where(
        Visit.patient_id.in_(patient_ids)
    ).order_by(Visit.created_at.desc())
    rows = (await db.execute(stmt)).all()

    my_visits_list = []
    for v, patient_name, doc in rows:
        rating = None
        if v.rating_stars:
            rating = VisitRating(
                stars=v.rating_stars,
                comment=v.rating_comment or "",
                at=v.rating_at.isoformat() if v.rating_at else v.created_at.isoformat(),
            )

        my_visits_list.append(
            MyVisit(
                id=v.id,
                created_at=v.created_at.isoformat(),
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
                diagnosis=v.diagnosis,
                medicines=[Medicine(**m) for m in (v.medicines or [])],
                rating=rating,
            )
        )
    return my_visits_list


async def rate_visit(db: AsyncSession, visit_id: int, req: RateVisitRequest, user: Profile) -> VisitRating:
    stmt = select(Visit, Patient).join(Patient, Visit.patient_id == Patient.id).where(
        Visit.id == visit_id
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise NotFoundException(message="Visit not found", code="not_found")
    visit, patient = row

    if patient.account_id != user.id:
        raise NotFoundException(message="Visit not found", code="not_found")

    if visit.rating_stars is not None:
        raise ConflictException(message="Visit has already been rated", code="already_rated")

    if not (1 <= req.stars <= 5):
        raise UnprocessableEntityException(message="Rating must be between 1 and 5 stars", code="bad_rating")

    now_utc = datetime.now(timezone.utc)
    visit.rating_stars = req.stars
    visit.rating_comment = req.comment.strip()[:300]
    visit.rating_at = now_utc

    await db.commit()

    return VisitRating(
        stars=visit.rating_stars,
        comment=visit.rating_comment,
        at=now_utc.isoformat(),
    )


async def get_my_follow_ups(db: AsyncSession, user: Profile) -> List[FollowUp]:
    p_stmt = select(Patient.id, Patient.name).where(Patient.account_id == user.id)
    patients = (await db.execute(p_stmt)).all()
    patient_map = {p_id: name for p_id, name in patients}
    if not patient_map:
        return []

    cutoff = date.today() - timedelta(days=30)
    v_stmt = select(Visit, Doctor).join(Doctor, Visit.doctor_id == Doctor.id).where(
        Visit.patient_id.in_(list(patient_map.keys())),
        Visit.follow_up_on.is_not(None),
        Visit.follow_up_on >= cutoff,
    ).order_by(Visit.follow_up_on.asc())
    rows = (await db.execute(v_stmt)).all()

    follow_ups = []
    for v, doc in rows:
        # Check if already booked
        v_date = v.created_at.date()
        chk = select(Appointment).where(
            Appointment.patient_id == v.patient_id,
            Appointment.doctor_id == v.doctor_id,
            Appointment.status != "cancelled",
            Appointment.date > v_date,
        )
        if not (await db.execute(chk)).first():
            follow_ups.append(
                FollowUp(
                    visit_id=v.id,
                    patient_id=v.patient_id,
                    patient_name=patient_map[v.patient_id],
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
                    due=str(v.follow_up_on),
                )
            )
    return follow_ups
