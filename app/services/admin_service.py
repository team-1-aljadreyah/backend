from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from collections import Counter
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import (
    NotFoundException,
    ConflictException,
    UnprocessableEntityException,
    ForbiddenException,
)
from app.database.models.profile import Profile, Doctor
from app.database.models.patient import Patient
from app.database.models.appointment import Appointment
from app.database.models.visit import Visit, Service
from app.database.models.finance import Payment
from app.database.models.governance import ClinicSettings, AuditLog, Notification
from app.schemas.admin import (
    StaffUser,
    CreateStaffRequest,
    UpdateStaffRequest,
    ClinicSettingsSchema,
    AuditEntry,
    ManagerOverview,
    AnalyticsSchema,
    AnalyticsTotals,
    AnalyticsDay,
    DoctorAnalytics,
    RatingsAnalytics,
    DoctorRatingSummary,
    RecentRating,
    AppNotification,
)
from app.schemas.service import ServiceSchema, ServiceInput
from app.schemas.finance import CountRow
from app.core.security import normalize_phone_local, get_password_hash
from app.services.audit_service import log_audit


async def list_staff_users(db: AsyncSession, viewer: Profile) -> List[StaffUser]:
    stmt = select(Profile).order_by(Profile.id)
    if viewer.role != "manager":
        stmt = stmt.where(Profile.role != "patient")

    users = (await db.execute(stmt)).scalars().all()
    return [
        StaffUser(
            id=u.id,
            name=u.name,
            phone=u.phone,
            role=u.role,
            active=bool(u.is_active),
        )
        for u in users
    ]


async def create_staff_user(db: AsyncSession, req: CreateStaffRequest, creator: Profile):
    if req.role in ("manager", "patient") and creator.role != "manager":
        raise ForbiddenException(message="Only managers can create manager or patient accounts", code="forbidden")

    phone = normalize_phone_local(req.phone)
    chk = select(Profile).where(Profile.phone == phone)
    if (await db.execute(chk)).scalar_one_or_none():
        raise ConflictException(message="Phone number is already registered", code="phone_taken")

    hashed_pw = get_password_hash(req.password)
    new_user = Profile(
        name=req.name.strip(),
        phone=phone,
        password_hash=hashed_pw,
        role=req.role,
    )

    if req.role == "patient":
        db.add(new_user)
        await db.flush()
        # Take over unlinked walk-in file if exists
        p_stmt = select(Patient).where(Patient.phone == phone, Patient.account_id.is_(None))
        p = (await db.execute(p_stmt)).scalar_one_or_none()
        if p:
            p.account_id = new_user.id
            p.relation = "self"
        else:
            new_p = Patient(
                name=req.name.strip(),
                phone=phone,
                account_id=new_user.id,
                relation="self",
                allergies=[],
                conditions=[],
            )
            db.add(new_p)
    elif req.role == "doctor":
        if not req.doctor:
            raise UnprocessableEntityException(message="Doctor profile details required", code="validation_error")
        day = {"branch": req.doctor.branch, "shift": "morning"}
        starting_days = [day, day, day, day, day, None, day]

        doc = Doctor(
            name=req.doctor.name_en.strip(),
            name_ar=req.name.strip(),
            specialty=req.doctor.specialty_en.strip(),
            specialty_ar=req.doctor.specialty_ar.strip(),
            fee=req.doctor.fee,
            new_minutes=20,
            followup_minutes=10,
            clinic_percent=30,
            service_percent=30,
            days=starting_days,
            absences=[],
            late_date=None,
            late_minutes=0,
        )
        db.add(doc)
        await db.flush()
        new_user.doctor_id = doc.id
        db.add(new_user)
    else:
        db.add(new_user)

    await db.flush()
    await log_audit(db, creator, "staff.create", req.name.strip())
    await db.commit()


async def update_staff_user(db: AsyncSession, user_id: int, req: UpdateStaffRequest, manager: Profile):
    stmt = select(Profile).where(Profile.id == user_id)
    target = (await db.execute(stmt)).scalar_one_or_none()
    if not target:
        raise NotFoundException(message="User not found", code="not_found")

    if req.phone:
        norm_phone = normalize_phone_local(req.phone)
        chk = select(Profile).where(Profile.phone == norm_phone, Profile.id != user_id)
        if (await db.execute(chk)).scalar_one_or_none():
            raise ConflictException(message="Phone number is already taken", code="phone_taken")
        target.phone = norm_phone

    if req.name and req.name.strip():
        target.name = req.name.strip()

    if req.new_password:
        target.password_hash = get_password_hash(req.new_password)

    await log_audit(db, manager, "staff.update", target.name)
    await db.commit()


async def set_staff_active(db: AsyncSession, user_id: int, active: bool, manager: Profile):
    stmt = select(Profile).where(Profile.id == user_id)
    target = (await db.execute(stmt)).scalar_one_or_none()
    if not target:
        raise NotFoundException(message="User not found", code="not_found")

    if not active:
        if target.id == manager.id:
            raise UnprocessableEntityException(message="Cannot disable yourself", code="cannot_disable_self")
        if target.role == "manager":
            mgr_stmt = select(func.count(Profile.id)).where(Profile.role == "manager", Profile.is_active == True)
            active_mgr_count = (await db.execute(mgr_stmt)).scalar() or 0
            if active_mgr_count <= 1:
                raise UnprocessableEntityException(message="Cannot disable the last manager", code="last_manager")

    target.is_active = active
    await log_audit(db, manager, "staff.enable" if active else "staff.disable", target.name)
    await db.commit()


async def get_clinic_settings(db: AsyncSession) -> ClinicSettingsSchema:
    stmt = select(ClinicSettings).where(ClinicSettings.id == 1)
    s = (await db.execute(stmt)).scalar_one_or_none()
    if not s:
        s = ClinicSettings(id=1)
        db.add(s)
        await db.commit()

    return ClinicSettingsSchema(
        cancel_hours=s.cancel_hours,
        no_show_limit=s.no_show_limit,
        deposit_amount=float(s.deposit_amount),
        prescription_days=s.prescription_days,
        usd_rate=float(s.usd_rate),
        welfare_discount_percent=float(getattr(s, "welfare_discount_percent", 25.0) or 25.0),
    )


async def update_clinic_settings(db: AsyncSession, req: ClinicSettingsSchema, user: Profile) -> ClinicSettingsSchema:
    stmt = select(ClinicSettings).where(ClinicSettings.id == 1)
    s = (await db.execute(stmt)).scalar_one_or_none()
    if not s:
        s = ClinicSettings(id=1)
        db.add(s)

    s.cancel_hours = req.cancel_hours
    s.no_show_limit = req.no_show_limit
    s.deposit_amount = req.deposit_amount
    s.prescription_days = req.prescription_days
    s.usd_rate = req.usd_rate
    s.welfare_discount_percent = req.welfare_discount_percent

    await log_audit(db, user, "settings.update", "")
    await db.commit()

    return req


async def list_audit_logs(db: AsyncSession, action: Optional[str] = None) -> List[AuditEntry]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(AuditLog.id.desc()).limit(200)
    entries = (await db.execute(stmt)).scalars().all()
    return [
        AuditEntry(
            id=e.id,
            at=e.at.isoformat(),
            user_name=e.user_name,
            role=e.role,
            action=e.action,
            target=e.target,
        )
        for e in entries
    ]


async def get_manager_overview(db: AsyncSession) -> ManagerOverview:
    today = date.today()
    a_stmt = select(Appointment).where(Appointment.date == today, Appointment.status != "cancelled")
    todays_appts = (await db.execute(a_stmt)).scalars().all()

    waiting = sum(1 for a in todays_appts if a.status == "arrived")
    done = sum(1 for a in todays_appts if a.status == "done")

    doc_count = (await db.execute(select(func.count(Doctor.id)))).scalar_one() or 0
    staff_count = (await db.execute(select(func.count(Profile.id)).where(Profile.role != "patient"))).scalar_one() or 0

    return ManagerOverview(
        appointments_today=len(todays_appts),
        waiting_now=waiting,
        visits_done_today=done,
        doctors=doc_count,
        staff=staff_count,
    )


async def get_analytics(db: AsyncSession, days: int) -> AnalyticsSchema:
    today = date.today()
    start_date = today - timedelta(days=days - 1)

    a_stmt = select(Appointment, Doctor.name_ar).join(Doctor, Appointment.doctor_id == Doctor.id).where(
        Appointment.date >= start_date,
        Appointment.date <= today,
    )
    appt_rows = (await db.execute(a_stmt)).all()
    all_appts = [r[0] for r in appt_rows]

    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc)

    # Payments
    p_stmt = select(Payment, Appointment.doctor_id).join(Appointment, Payment.appointment_id == Appointment.id).where(
        Payment.at >= start_dt,
        Payment.at <= end_dt,
    )
    payment_rows = (await db.execute(p_stmt)).all()

    def get_dinars(p: Payment) -> float:
        if p.currency != "IQD":
            return 0.0
        return float(p.amount) if p.kind == "payment" else -float(p.amount)

    by_day_list = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        d_str = str(d)
        d_appts = [a for a in all_appts if a.date == d]
        d_visited = [a for a in d_appts if a.status in ("arrived", "in_progress", "done")]
        d_payments = [r[0] for r in payment_rows if r[0].at.date() == d]

        sum_collected = sum(get_dinars(p) for p in d_payments)
        sum_cash = sum(get_dinars(p) for p in d_payments if p.method == "cash")
        sum_online = sum(get_dinars(p) for p in d_payments if p.method == "online")

        by_day_list.append(
            AnalyticsDay(
                date=d_str,
                visits=len(d_visited),
                followups=sum(1 for a in d_visited if a.kind == "followup"),
                no_shows=sum(1 for a in d_appts if a.status == "no_show"),
                cancelled=sum(1 for a in d_appts if a.status == "cancelled"),
                collected=sum_collected,
                cash=sum_cash,
                online=sum_online,
            )
        )

    # By doctor
    d_stmt = select(Doctor).order_by(Doctor.id)
    doctors = (await db.execute(d_stmt)).scalars().all()
    by_doc_list = []
    visited_all = [a for a in all_appts if a.status in ("arrived", "in_progress", "done")]

    for doc in doctors:
        v_count = sum(1 for a in visited_all if a.doctor_id == doc.id)
        doc_col = sum(get_dinars(p) for p, d_id in payment_rows if d_id == doc.id)
        by_doc_list.append(DoctorAnalytics(label=doc.name_ar, visits=v_count, collected=doc_col))
    by_doc_list.sort(key=lambda x: x.visits, reverse=True)

    # First visits ever in range (new_patients)
    fv_stmt = select(Appointment.patient_id, func.min(Appointment.date)).where(
        Appointment.status.in_(["arrived", "in_progress", "done"])
    ).group_by(Appointment.patient_id)
    first_visits = (await db.execute(fv_stmt)).all()
    new_patients_count = sum(1 for _, f_date in first_visits if start_date <= f_date <= today)

    # Totals collected
    tot_collected = {"IQD": 0.0, "USD": 0.0}
    for p, _ in payment_rows:
        amt = float(p.amount) if p.kind == "payment" else -float(p.amount)
        tot_collected[p.currency] += amt

    # By hour
    hour_counts = Counter(a.time[:2] for a in all_appts if a.time)
    by_hour = [CountRow(label=h, count=c) for h, c in sorted(hour_counts.items())]

    # By method
    by_method = {
        "cash": sum(get_dinars(p) for p, _ in payment_rows if p.method == "cash"),
        "online": sum(get_dinars(p) for p, _ in payment_rows if p.method == "online"),
    }

    # Top diagnoses
    v_stmt = select(Visit.diagnosis).where(Visit.created_at >= start_dt, Visit.created_at <= end_dt)
    diagnoses = (await db.execute(v_stmt)).scalars().all()
    diag_counts = Counter(d for d in diagnoses if d)
    top_diagnoses = [CountRow(label=d, count=c) for d, c in diag_counts.most_common(5)]

    # Ratings
    r_stmt = select(Visit, Doctor.name_ar).join(Doctor, Visit.doctor_id == Doctor.id).where(
        Visit.rating_stars.is_not(None),
        Visit.created_at >= start_dt,
        Visit.created_at <= end_dt,
    )
    rated_visits = (await db.execute(r_stmt)).all()

    ratings_by_doc = []
    for doc in doctors:
        doc_ratings = [v.rating_stars for v, _ in rated_visits if v.doctor_id == doc.id and v.rating_stars]
        if doc_ratings:
            avg = round(sum(doc_ratings) / len(doc_ratings), 1)
            ratings_by_doc.append(DoctorRatingSummary(label=doc.name_ar, average=avg, count=len(doc_ratings)))
    ratings_by_doc.sort(key=lambda x: x.average, reverse=True)

    recent_ratings = [
        RecentRating(
            stars=v.rating_stars,
            comment=v.rating_comment or "",
            doctor=doc_name,
            at=v.rating_at.isoformat() if v.rating_at else v.created_at.isoformat(),
        )
        for v, doc_name in sorted(rated_visits, key=lambda x: x[0].rating_at or x[0].created_at, reverse=True)
        if v.rating_comment
    ][:5]

    return AnalyticsSchema(
        from_date=str(start_date),
        to=str(today),
        totals=AnalyticsTotals(
            appointments=len(all_appts),
            visits=len(visited_all),
            no_shows=sum(1 for a in all_appts if a.status == "no_show"),
            cancelled=sum(1 for a in all_appts if a.status == "cancelled"),
            walk_ins=sum(1 for a in all_appts if not a.time),
            followups=sum(1 for a in visited_all if a.kind == "followup"),
            new_patients=new_patients_count,
            collected=tot_collected,
        ),
        by_day=by_day_list,
        by_doctor=by_doc_list,
        by_hour=by_hour,
        by_method=by_method,
        top_diagnoses=top_diagnoses,
        ratings=RatingsAnalytics(by_doctor=ratings_by_doc, recent=recent_ratings),
    )


async def list_services(db: AsyncSession) -> List[ServiceSchema]:
    stmt = select(Service).order_by(Service.id)
    services = (await db.execute(stmt)).scalars().all()
    return [
        ServiceSchema(
            id=s.id,
            name=s.name,
            name_ar=s.name_ar,
            kind=s.kind,
            price=float(s.price),
            currency=s.currency,
            template=s.template,
        )
        for s in services
    ]


async def create_service(db: AsyncSession, req: ServiceInput, user: Profile):
    svc = Service(
        name=req.name.strip(),
        name_ar=req.name_ar.strip(),
        kind=req.kind,
        price=req.price,
        currency=req.currency,
        template=None,
    )
    db.add(svc)
    await log_audit(db, user, "service.create", req.name_ar.strip())
    await db.commit()


async def update_service(db: AsyncSession, service_id: int, req: ServiceInput, user: Profile):
    stmt = select(Service).where(Service.id == service_id)
    svc = (await db.execute(stmt)).scalar_one_or_none()
    if not svc:
        raise NotFoundException(message="Service not found", code="not_found")

    svc.name = req.name.strip()
    svc.name_ar = req.name_ar.strip()
    svc.kind = req.kind
    svc.price = req.price
    svc.currency = req.currency

    await log_audit(db, user, "service.update", req.name_ar.strip())
    await db.commit()


async def get_my_notifications(db: AsyncSession, user: Profile) -> List[AppNotification]:
    stmt = select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc())
    items = (await db.execute(stmt)).scalars().all()
    return [
        AppNotification(
            id=n.id,
            type=n.type,
            params=dict(n.params or {}),
            at=n.at.isoformat(),
            read=n.read,
        )
        for n in items
    ]


async def mark_notifications_read(db: AsyncSession, user: Profile):
    await db.execute(
        update(Notification).where(Notification.user_id == user.id).values(read=True)
    )
    await db.commit()
