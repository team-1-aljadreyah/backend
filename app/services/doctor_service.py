from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundException, ConflictException, ForbiddenException
from app.database.models.profile import Doctor, Profile
from app.database.models.appointment import Appointment
from app.database.models.finance import Payment
from app.schemas.doctor import (
    DoctorSchema,
    DoctorDay,
    WorkDay,
    Slot,
    DoctorSchedule,
    DoctorLate,
    UpdateScheduleRequest,
    ScreenDoctor,
)
from app.services.audit_service import log_audit
from app.services.notification_service import notify_patient

SHIFTS = {
    "morning": {"start": "09:00", "end": "13:00"},
    "evening": {"start": "16:00", "end": "20:00"},
}

ACTIVE_STATUSES = ["booked", "arrived", "in_progress", "done"]


def to_minutes(time_str: str) -> int:
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def to_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def get_weekday_idx(d: date) -> int:
    # Python weekday: Monday is 0, Sunday is 6.
    # Javascript / Frontend weekday: Sunday is 0, Monday is 1, ..., Saturday is 6.
    return (d.weekday() + 1) % 7


def get_ticket_label(doctor_id: int, all_doctor_ids: List[int], ticket_num: Optional[int]) -> Optional[str]:
    if not ticket_num:
        return None
    try:
        idx = all_doctor_ids.index(doctor_id)
    except ValueError:
        idx = 0
    letter = chr(65 + max(0, idx))
    return f"{letter}-{ticket_num:03d}"


async def list_public_doctors(db: AsyncSession) -> List[DoctorSchema]:
    stmt = select(Doctor).order_by(Doctor.id)
    res = await db.execute(stmt)
    doctors = res.scalars().all()
    return [
        DoctorSchema(
            id=d.id,
            name=d.name,
            name_ar=d.name_ar,
            specialty=d.specialty,
            specialty_ar=d.specialty_ar,
            fee=float(d.fee),
            new_minutes=d.new_minutes,
            followup_minutes=d.followup_minutes,
        )
        for d in doctors
    ]


async def get_queue_screen(db: AsyncSession) -> List[ScreenDoctor]:
    today = date.today()
    weekday_idx = get_weekday_idx(today)

    stmt = select(Doctor).order_by(Doctor.id)
    res = await db.execute(stmt)
    all_doctors = res.scalars().all()
    all_doc_ids = [d.id for d in all_doctors]

    screen_list = []
    for doc in all_doctors:
        days = doc.days or []
        if weekday_idx >= len(days) or not days[weekday_idx]:
            continue

        work_day = days[weekday_idx]
        branch = work_day.get("branch", "main")
        absent = str(today) in (doc.absences or [])
        late_minutes = doc.late_minutes if doc.late_date == today else 0

        # Query queue for doctor today
        q_stmt = (
            select(Appointment)
            .where(
                Appointment.doctor_id == doc.id,
                Appointment.date == today,
                Appointment.status.in_(["arrived", "in_progress"]),
            )
            .order_by(
                # in_progress first, then arrival_order
                Appointment.status.desc(),
                Appointment.arrival_order.asc(),
            )
        )
        q_res = await db.execute(q_stmt)
        queue = q_res.scalars().all()

        in_room = next((a for a in queue if a.status == "in_progress"), None)
        waiting = [a for a in queue if a.status == "arrived"]

        now_ticket = get_ticket_label(doc.id, all_doc_ids, in_room.ticket) if in_room else None
        called_at_str = in_room.called_at.isoformat() if in_room and in_room.called_at else None

        next_tickets = [
            get_ticket_label(doc.id, all_doc_ids, a.ticket)
            for a in waiting[:4]
            if a.ticket is not None
        ]

        screen_list.append(
            ScreenDoctor(
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
                branch=branch,
                absent=absent,
                late_minutes=late_minutes,
                now=now_ticket,
                called_at=called_at_str,
                next=next_tickets,
                waiting=len(waiting),
            )
        )

    return screen_list


async def get_doctor_days(db: AsyncSession, doctor_id: int) -> List[DoctorDay]:
    stmt = select(Doctor).where(Doctor.id == doctor_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise NotFoundException(message="Doctor not found", code="not_found")

    today = date.today()
    days_result = []
    doc_days = doc.days or []
    absences = doc.absences or []

    for i in range(14):
        cur_date = today + timedelta(days=i)
        w_idx = get_weekday_idx(cur_date)
        work_info = None
        if w_idx < len(doc_days) and doc_days[w_idx]:
            d_item = doc_days[w_idx]
            sh = d_item.get("shift", "morning")
            sh_fallback = SHIFTS.get(sh, SHIFTS["morning"])
            work_info = WorkDay(
                branch=d_item["branch"],
                shift=d_item["shift"],
                start=d_item.get("start") or sh_fallback["start"],
                end=d_item.get("end") or sh_fallback["end"],
            )

        days_result.append(
            DoctorDay(
                date=str(cur_date),
                work=work_info,
                absent=str(cur_date) in absences,
            )
        )

    return days_result


async def get_doctor_slots(
    db: AsyncSession,
    doctor_id: int,
    target_date_str: str,
    kind: str,
    ignore_appointment_id: Optional[int] = None,
) -> List[Slot]:
    stmt = select(Doctor).where(Doctor.id == doctor_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise NotFoundException(message="Doctor not found", code="not_found")

    target_date = date.fromisoformat(target_date_str)
    w_idx = get_weekday_idx(target_date)
    doc_days = doc.days or []

    if target_date_str in (doc.absences or []) or w_idx >= len(doc_days) or not doc_days[w_idx]:
        return []

    work_day = doc_days[w_idx]
    shift_info = SHIFTS.get(work_day["shift"], SHIFTS["morning"])
    slot_len = doc.new_minutes if kind == "new" else doc.followup_minutes

    # Get active bookings for doctor on date
    b_stmt = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.date == target_date,
        Appointment.status.in_(ACTIVE_STATUSES),
        Appointment.time != "",
    )
    if ignore_appointment_id:
        b_stmt = b_stmt.where(Appointment.id != ignore_appointment_id)

    b_res = await db.execute(b_stmt)
    busy_appts = b_res.scalars().all()

    busy_intervals = []
    for a in busy_appts:
        appt_len = doc.new_minutes if a.kind == "new" else doc.followup_minutes
        start_m = to_minutes(a.time)
        busy_intervals.append((start_m, start_m + appt_len))

    now_dt = datetime.now()
    now_minutes = -1
    if target_date == date.today():
        now_minutes = now_dt.hour * 60 + now_dt.minute

    slots = []
    start_str = work_day.get("start") or shift_info["start"]
    end_str = work_day.get("end") or shift_info["end"]
    start_shift = to_minutes(start_str)
    end_shift = to_minutes(end_str)

    curr = start_shift
    while curr + slot_len <= end_shift:
        time_str = to_time(curr)
        is_future = curr > now_minutes
        overlap = any(curr < end and curr + slot_len > start for start, end in busy_intervals)
        available = is_future and not overlap

        slots.append(Slot(time=time_str, available=available))
        curr += slot_len

    return slots


async def list_doctor_schedules(db: AsyncSession) -> List[DoctorSchedule]:
    stmt = select(Doctor).order_by(Doctor.id)
    res = await db.execute(stmt)
    doctors = res.scalars().all()
    today_str = str(date.today())

    schedules = []
    for doc in doctors:
        days = []
        for d in (doc.days or []):
            if not d:
                days.append(None)
            else:
                sh = d.get("shift", "morning")
                sh_fallback = SHIFTS.get(sh, SHIFTS["morning"])
                days.append(
                    WorkDay(
                        branch=d["branch"],
                        shift=d["shift"],
                        start=d.get("start") or sh_fallback["start"],
                        end=d.get("end") or sh_fallback["end"],
                    )
                )
        absences = [a for a in (doc.absences or []) if a >= today_str]
        late = None
        if doc.late_date == date.today() and doc.late_minutes > 0:
            late = DoctorLate(date=today_str, minutes=doc.late_minutes)

        schedules.append(
            DoctorSchedule(
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
                clinic_percent=float(doc.clinic_percent),
                service_percent=float(doc.service_percent),
                days=days,
                absences=absences,
                late=late,
            )
        )
    return schedules


async def update_schedule(db: AsyncSession, doctor_id: int, req: UpdateScheduleRequest, user: Profile):
    stmt = select(Doctor).where(Doctor.id == doctor_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise NotFoundException(message="Doctor not found", code="not_found")

    doc.fee = req.fee
    doc.clinic_percent = req.clinic_percent
    doc.service_percent = req.service_percent
    doc.new_minutes = req.new_minutes
    doc.followup_minutes = req.followup_minutes
    doc.days = [d.model_dump() if d else None for d in req.days]

    await log_audit(db, user, "doctor.update", doc.name_ar)
    await db.commit()


async def mark_doctor_absent(db: AsyncSession, doctor_id: int, date_str: str, user: Profile) -> int:
    today_str = str(date.today())
    if date_str < today_str:
        raise ConflictException(message="Cannot mark absence for past dates", code="past_date")

    stmt = select(Doctor).where(Doctor.id == doctor_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise NotFoundException(message="Doctor not found", code="not_found")

    absences = list(doc.absences or [])
    if date_str not in absences:
        absences.append(date_str)
        doc.absences = absences

    # Cancel affected appointments
    target_date = date.fromisoformat(date_str)
    a_stmt = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.date == target_date,
        Appointment.status == "booked",
    )
    a_res = await db.execute(a_stmt)
    affected = a_res.scalars().all()

    for appt in affected:
        appt.status = "cancelled"
        appt.cancel_reason = "doctor_absent"

        # Refund online payments
        p_stmt = select(Payment).where(
            Payment.appointment_id == appt.id,
            Payment.method == "online",
            Payment.kind == "payment",
        )
        p_res = await db.execute(p_stmt)
        payments = p_res.scalars().all()
        for p in payments:
            # Check if already refunded
            chk = select(Payment).where(Payment.ref_id == p.id)
            chk_res = await db.execute(chk)
            if not chk_res.scalar_one_or_none():
                refund_p = Payment(
                    appointment_id=appt.id,
                    amount=p.amount,
                    currency=p.currency,
                    method="online",
                    kind="refund",
                    by=user.name,
                    reason="doctor_absent",
                    ref_id=p.id,
                    key=f"refund:{p.id}",
                )
                db.add(refund_p)

        await notify_patient(
            db,
            appt.patient_id,
            f"absent:{appt.id}",
            "doctor_absent",
            {"doctor": doc.name_ar, "date": date_str, "time": appt.time},
        )

    await log_audit(db, user, "doctor.absent", f"{doc.name_ar} · {date_str}")
    await db.commit()
    return len(affected)


async def mark_doctor_late(db: AsyncSession, doctor_id: int, minutes: int, user: Profile) -> int:
    stmt = select(Doctor).where(Doctor.id == doctor_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise NotFoundException(message="Doctor not found", code="not_found")

    today = date.today()
    doc.late_date = today
    doc.late_minutes = minutes

    a_stmt = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.date == today,
        Appointment.status.in_(["booked", "arrived"]),
    )
    a_res = await db.execute(a_stmt)
    affected = a_res.scalars().all()

    for appt in affected:
        await notify_patient(
            db,
            appt.patient_id,
            f"late:{appt.id}:{minutes}",
            "doctor_late",
            {"doctor": doc.name_ar, "minutes": minutes},
        )

    await log_audit(db, user, "doctor.late", f"{doc.name_ar} · {minutes}")
    await db.commit()
    return len(affected)
