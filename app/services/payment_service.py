import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundException, ConflictException, UnprocessableEntityException, ForbiddenException
from app.database.models.appointment import Appointment
from app.database.models.patient import Patient
from app.database.models.profile import Profile, Doctor
from app.database.models.finance import Payment, PaymentSession, InvoiceItem
from app.schemas.finance import PaymentSessionSchema, PaymentLogEntry
from app.schemas.common import PaymentStatus
from app.services import finance_service, admin_service
from app.integrations.qi_gateway import qi_gateway


async def clean_expired_unpaid_appointments(db: AsyncSession):
    now = datetime.now(timezone.utc)
    stmt = select(Appointment).where(
        Appointment.status == "booked",
        Appointment.pay_by.isnot(None),
        Appointment.pay_by < now,
    )
    appts = (await db.execute(stmt)).scalars().all()
    for a in appts:
        # Check if paid online
        stmt_p = select(Payment).where(
            Payment.appointment_id == a.id,
            Payment.kind == "payment",
            Payment.method == "online",
        )
        paid = (await db.execute(stmt_p)).scalars().first()
        if paid:
            a.pay_by = None
        else:
            a.status = "cancelled"
            a.cancel_reason = "unpaid"
            a.pay_by = None

            # Mark any open payment sessions as canceled
            stmt_s = select(PaymentSession).where(
                PaymentSession.appointment_id == a.id,
                PaymentSession.status == "created",
            )
            sessions = (await db.execute(stmt_s)).scalars().all()
            for s in sessions:
                s.status = "canceled"
    if appts:
        await db.commit()


def _session_to_schema(s: PaymentSession, pay_by: Optional[datetime] = None) -> PaymentSessionSchema:
    return PaymentSessionSchema(
        payment_id=s.id,
        appointment_id=s.appointment_id,
        amount=float(s.amount),
        currency=s.currency,
        status=s.status,
        form_url=s.form_url,
        created_at=s.created_at.isoformat() if s.created_at else "",
        pay_by=pay_by.isoformat() if pay_by else None,
    )


async def create_payment_session(
    db: AsyncSession,
    appointment_id: int,
    return_url: str,
    idempotency_key: Optional[str],
    user: Profile,
    pay_choice: str = "full",
) -> PaymentSessionSchema:
    # Auto-clean expired first
    await clean_expired_unpaid_appointments(db)

    stmt = select(Appointment).where(Appointment.id == appointment_id)
    appt = (await db.execute(stmt)).scalar_one_or_none()
    if not appt:
        raise NotFoundException("Appointment not found", "not_found")

    # If patient, verify ownership
    if user.role == "patient":
        stmt_p = select(Patient).where(Patient.id == appt.patient_id)
        p = (await db.execute(stmt_p)).scalar_one_or_none()
        if not p or p.account_id != user.id:
            raise ForbiddenException("Cannot pay for another patient's appointment", "forbidden")

    if appt.status != "booked":
        raise ConflictException("Appointment is not in booked state", "cancelled")

    # Check idempotency
    if idempotency_key:
        stmt_existing = select(PaymentSession).where(
            or_(
                PaymentSession.key == idempotency_key,
                PaymentSession.id == idempotency_key,
            )
        )
        existing = (await db.execute(stmt_existing)).scalar_one_or_none()
        if existing:
            if existing.user_id != user.id or existing.appointment_id != appointment_id:
                raise ConflictException("Idempotency key already used with different parameters", "idempotency_conflict")
            return _session_to_schema(existing, appt.pay_by)

    # Ensure visit fee item exists on this appointment
    stmt_items = select(InvoiceItem).where(InvoiceItem.appointment_id == appointment_id)
    existing_items = (await db.execute(stmt_items)).scalars().all()
    if not existing_items:
        stmt_doc = select(Doctor).where(Doctor.id == appt.doctor_id)
        doc = (await db.execute(stmt_doc)).scalar_one_or_none()
        doc_fee = float(doc.fee) if doc and doc.fee else 25000.0
        fee_item = InvoiceItem(
            appointment_id=appointment_id,
            label="Visit fee",
            label_ar="رسوم الكشف",
            kind="visit",
            price=doc_fee,
            currency="IQD",
        )
        db.add(fee_item)
        await db.flush()

    # Compute balance
    money = await finance_service.get_money_summary(db, appointment_id)
    owed = money.balance.get("IQD", 0.0)

    if owed <= 0:
        raise ConflictException("No outstanding balance for this appointment", "zero_balance")

    settings = await admin_service.get_clinic_settings(db)
    deposit_val = float(getattr(settings, "deposit_amount", 10000.0))

    if pay_choice == "deposit":
        amount = min(deposit_val, owed)
    else:
        amount = owed

    # Ensure amount does not exceed outstanding balance
    amount = min(float(amount), owed)

    # Check deposit requirement
    from app.services.appointment_service import get_patient_booking_rules
    rules = await get_patient_booking_rules(db, appt.patient_id)
    if rules.deposit_required and not appt.pay_by:
        appt.pay_by = datetime.now(timezone.utc) + timedelta(minutes=15)

    request_id = str(uuid.uuid4())
    finish_url = return_url or "https://alrahma.ama8.uk/account/payment"
    sep = "&" if "?" in finish_url else "?"
    full_finish_url = f"{finish_url}{sep}payment={request_id}"

    # Initiate Qi Card Payment Gateway Sandbox request
    qi_res = await qi_gateway.create_payment(
        request_id=request_id,
        amount=amount,
        currency="IQD",
        finish_payment_url=full_finish_url,
        notification_url="https://api.ama8.uk/payments/qi-webhook",
        locale="ar_IQ",
    )

    qi_payment_id = qi_res.get("paymentId") if qi_res else None
    form_url = qi_res.get("formUrl") if qi_res else None

    session_id = request_id
    if not form_url:
        form_url = f"/pay/demo?payment={session_id}"

    session_key = idempotency_key or request_id

    session = PaymentSession(
        id=session_id,
        appointment_id=appointment_id,
        user_id=user.id,
        amount=amount,
        currency="IQD",
        status="created",
        form_url=form_url,
        return_url=return_url or "",
        key=session_key,
        created_at=datetime.now(timezone.utc),
        outcome=qi_payment_id,  # Track Qi's internal paymentId
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    await db.refresh(appt)

    return _session_to_schema(session, appt.pay_by)


async def get_payment_session(
    db: AsyncSession,
    payment_id: str,
    user: Profile,
) -> PaymentSessionSchema:
    stmt = select(PaymentSession).where(
        or_(
            PaymentSession.id == payment_id,
            PaymentSession.key == payment_id,
            PaymentSession.outcome == payment_id,
        )
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise NotFoundException("Payment session not found", "not_found")

    stmt_appt = select(Appointment).where(Appointment.id == session.appointment_id)
    appt = (await db.execute(stmt_appt)).scalar_one_or_none()
    if not appt:
        raise NotFoundException("Associated appointment not found", "not_found")

    if user.role == "patient":
        stmt_p = select(Patient).where(Patient.id == appt.patient_id)
        p = (await db.execute(stmt_p)).scalar_one_or_none()
        if not p or (p.account_id != user.id and session.user_id != user.id):
            raise ForbiddenException("Cannot view payment of another patient", "forbidden")

    # If created, verify transaction status directly with QiCard Sandbox Gateway
    if session.status == "created":
        if appt.status == "cancelled":
            session.status = "canceled"
            await db.commit()
        else:
            # Query Qi gateway status using Qi's paymentId (stored in outcome) or session.id
            target_qi_id = session.outcome if (session.outcome and "-" in session.outcome and len(session.outcome) >= 32) else session.id
            qi_data = await qi_gateway.get_payment_status(target_qi_id)
            if qi_data:
                raw_status = (qi_data.get("status") or "").upper()
                is_canceled = bool(qi_data.get("canceled", False))
                if is_canceled:
                    session.status = "canceled"
                    await db.commit()
                elif raw_status == "SUCCESS":
                    session.status = "success"
                    session.settled_at = datetime.now(timezone.utc)
                    from app.schemas.finance import PayRequest
                    await finance_service.take_payment(
                        db,
                        session.appointment_id,
                        PayRequest(amount=float(session.amount), currency="IQD"),
                        "online",
                        user,
                        ref_key=f"gateway:{session.id}",
                    )
                    appt.pay_by = None
                    await db.commit()
                    await db.refresh(session)
                    await db.refresh(appt)
                elif raw_status == "FAILED":
                    session.status = "failed"
                    await db.commit()
                elif raw_status == "AUTHENTICATION_FAILED":
                    session.status = "authentication_failed"
                    await db.commit()
            elif session.outcome in ("success", "failed", "authentication_failed", "canceled"):
                # Simulation / Test hook
                session.status = session.outcome
                if session.status == "success":
                    from app.schemas.finance import PayRequest
                    await finance_service.take_payment(
                        db,
                        session.appointment_id,
                        PayRequest(amount=float(session.amount), currency="IQD"),
                        "online",
                        user,
                        ref_key=f"gateway:{session.id}",
                    )
                    appt.pay_by = None
                    session.settled_at = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(session)
                await db.refresh(appt)

    return _session_to_schema(session, appt.pay_by)


async def simulate_gateway_outcome(
    db: AsyncSession,
    payment_id: str,
    outcome: PaymentStatus,
    user: Optional[Profile] = None,
) -> PaymentSessionSchema:
    from app.core.config import settings
    if settings.APP_ENV == "production":
        raise ForbiddenException("Payment simulation is disabled in production environments", "simulation_disabled")

    if user and user.role not in ("manager", "accountant") and settings.APP_ENV not in ("testing", "development"):
        raise ForbiddenException("Only managers or accountants can simulate payment outcomes", "forbidden")

    stmt = select(PaymentSession).where(PaymentSession.id == payment_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        raise NotFoundException("Payment session not found", "not_found")

    stmt_appt = select(Appointment).where(Appointment.id == session.appointment_id)
    appt = (await db.execute(stmt_appt)).scalar_one_or_none()

    session.outcome = outcome
    session.status = outcome
    session.settled_at = datetime.now(timezone.utc)

    if outcome == "success" and appt:
        if appt.status == "cancelled":
            session.status = "canceled"
        else:
            from app.schemas.finance import PayRequest
            actor = user
            if not actor:
                stmt_u = select(Profile).where(Profile.id == session.user_id)
                actor = (await db.execute(stmt_u)).scalar_one_or_none()
            if not actor:
                stmt_m = select(Profile).where(Profile.role == "manager")
                actor = (await db.execute(stmt_m)).scalars().first()

            await finance_service.take_payment(
                db,
                session.appointment_id,
                PayRequest(amount=float(session.amount), currency="IQD"),
                "online",
                actor,
                ref_key=f"gateway:{session.id}",
            )
            appt.pay_by = None

    await db.commit()
    await db.refresh(session)
    return _session_to_schema(session, appt.pay_by if appt else None)


async def get_patient_payment_history(
    db: AsyncSession,
    user: Profile,
    limit: int = 50,
    offset: int = 0,
    patient_id: Optional[int] = None,
) -> Dict[str, Any]:
    # Determine target patients strictly by authorization
    if user.role == "patient":
        stmt_p = select(Patient.id).where(Patient.account_id == user.id)
        family_ids = (await db.execute(stmt_p)).scalars().all()
        if patient_id:
            if patient_id not in family_ids:
                raise ForbiddenException("Cannot view payment history of other patients", "forbidden")
            target_patient_ids = [patient_id]
        else:
            target_patient_ids = family_ids
    elif user.role in ("manager", "accountant", "reception"):
        # Authorized financial / front-desk staff
        if patient_id:
            target_patient_ids = [patient_id]
        elif user.role in ("manager", "accountant"):
            stmt_all = select(Patient.id)
            target_patient_ids = (await db.execute(stmt_all)).scalars().all()
        else:
            # Reception querying /me/payments without patient_id: return own family
            stmt_p = select(Patient.id).where(Patient.account_id == user.id)
            target_patient_ids = (await db.execute(stmt_p)).scalars().all()
    else:
        # Non-financial staff (reception, doctor, pharmacy, lab) querying /me/payments
        # must NOT receive all clinic records. Only their own family records if they have an account.
        stmt_p = select(Patient.id).where(Patient.account_id == user.id)
        target_patient_ids = (await db.execute(stmt_p)).scalars().all()
        if patient_id:
            if patient_id not in target_patient_ids:
                raise ForbiddenException("Staff role not authorized to view patient financial ledger", "forbidden")
            target_patient_ids = [patient_id]

    if not target_patient_ids:
        return {"items": [], "total": 0}

    # Get appointment IDs
    stmt_appts = (
        select(Appointment, Patient.name, Doctor.name_ar)
        .join(Patient, Appointment.patient_id == Patient.id)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .where(Appointment.patient_id.in_(target_patient_ids))
    )
    appt_data = (await db.execute(stmt_appts)).all()
    appt_map = {
        a.id: {
            "appointment_id": a.id,
            "patient_name": p_name,
            "doctor_name": d_name,
            "appointment_date": str(a.date),
            "appointment_time": a.time,
        }
        for a, p_name, d_name in appt_data
    }
    appointment_ids = list(appt_map.keys())

    if not appointment_ids:
        return {"items": [], "total": 0}

    # 1. Real payments (money moved)
    stmt_payments = select(Payment).where(Payment.appointment_id.in_(appointment_ids))
    payments = (await db.execute(stmt_payments)).scalars().all()

    entries: List[PaymentLogEntry] = []
    for p in payments:
        info = appt_map.get(p.appointment_id, {})
        entries.append(
            PaymentLogEntry(
                id=f"payment-{p.id}",
                kind=p.kind,
                status=None,
                at=p.at.isoformat() if p.at else "",
                amount=float(p.amount),
                currency=p.currency,
                method=p.method,
                receipt_no=p.id,
                by=p.by,
                reason=p.reason or "",
                appointment_id=p.appointment_id,
                patient_name=info.get("patient_name", ""),
                doctor_name=info.get("doctor_name", ""),
                appointment_date=info.get("appointment_date", ""),
                appointment_time=info.get("appointment_time", ""),
            )
        )

    # 2. Online attempts that didn't go through (status != success)
    stmt_sessions = select(PaymentSession).where(
        PaymentSession.appointment_id.in_(appointment_ids),
        PaymentSession.status != "success",
    )
    sessions = (await db.execute(stmt_sessions)).scalars().all()
    for s in sessions:
        info = appt_map.get(s.appointment_id, {})
        entries.append(
            PaymentLogEntry(
                id=f"attempt-{s.id}",
                kind="attempt",
                status=s.status,
                at=s.created_at.isoformat() if s.created_at else "",
                amount=float(s.amount),
                currency=s.currency,
                method="online",
                receipt_no=None,
                by=user.name,
                reason="",
                appointment_id=s.appointment_id,
                patient_name=info.get("patient_name", ""),
                doctor_name=info.get("doctor_name", ""),
                appointment_date=info.get("appointment_date", ""),
                appointment_time=info.get("appointment_time", ""),
            )
        )

    # Sort newest first
    entries.sort(key=lambda x: x.at, reverse=True)
    total = len(entries)
    paginated = entries[offset : offset + limit]
    return {"items": [e.model_dump() for e in paginated], "total": total}
