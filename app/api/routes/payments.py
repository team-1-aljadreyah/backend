from typing import Optional
from fastapi import APIRouter, Depends, Header, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.envelope import success_response
from sqlalchemy import select
from app.database.models.profile import Profile
from app.schemas.finance import StartPaymentRequest, PaymentSessionSchema
from app.schemas.common import PaymentStatus
from app.services import payment_service, finance_service

router = APIRouter(tags=["Payments & Qi Gateway"])


class ReversePaymentRequest(BaseModel):
    reason: str


@router.post("/appointments/{appointment_id}/payments")
async def start_payment(
    appointment_id: int,
    req: StartPaymentRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_idempotency_key_header: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    key = req.idempotency_key or idempotency_key_header or x_idempotency_key_header
    session = await payment_service.create_payment_session(
        db=db,
        appointment_id=appointment_id,
        return_url=req.return_url,
        idempotency_key=key,
        user=user,
    )
    return success_response(session.model_dump())


@router.get("/payments/{payment_id}")
async def get_payment_status(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    session = await payment_service.get_payment_session(db, payment_id, user)
    return success_response(session.model_dump())


@router.post("/payments/{payment_id}/simulate")
async def simulate_payment_outcome(
    payment_id: str,
    outcome: PaymentStatus = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    from app.core.config import settings
    from app.core.exceptions import ForbiddenException
    if settings.APP_ENV == "production":
        raise ForbiddenException("Payment simulation is disabled in production", "simulation_disabled")
    if user.role not in ("manager", "accountant") and settings.APP_ENV not in ("testing", "development"):
        raise ForbiddenException("Access denied to payment simulation", "forbidden")

    session = await payment_service.simulate_gateway_outcome(db, payment_id, outcome, user)
    return success_response(session.model_dump())


@router.post("/payments/{payment_id}/reverse")
async def reverse_payment(
    payment_id: int,
    req: ReversePaymentRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("accountant", "manager")),
):
    await finance_service.reverse_payment(db, payment_id, req.reason, user)
    return success_response(None)


@router.post("/payments/qi-webhook")
async def qi_payment_webhook(
    payload: dict = Body(default={}),
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    db: AsyncSession = Depends(get_db),
):
    from app.core.config import settings
    from app.core.exceptions import UnauthorizedException, BadRequestException
    from app.integrations.qi_gateway import qi_gateway
    from app.database.models.finance import PaymentSession
    from app.database.models.appointment import Appointment
    from app.database.models.profile import Profile
    from app.services import finance_service
    from app.services.realtime_service import record_outbox_event
    from datetime import datetime, timezone
    from decimal import Decimal

    payment_id = payload.get("paymentId") or payload.get("requestId")
    if not payment_id:
        raise BadRequestException("Missing paymentId or requestId in webhook payload", "invalid_payload")

    amount = payload.get("amount")
    currency = payload.get("currency", "IQD")
    creation_date = payload.get("creationDate", "")
    status_str = (payload.get("status") or "").upper()

    # 1. RSA-SHA256 signature verification if signature & key available
    if x_signature and settings.QI_WEBHOOK_PUBLIC_KEY_PEM:
        is_valid = qi_gateway.verify_webhook_signature(
            signature_b64=x_signature,
            payment_id=str(payment_id),
            amount=amount if amount is not None else "0",
            currency=currency,
            creation_date=str(creation_date),
            status=status_str,
        )
        if is_valid is False:
            raise UnauthorizedException("Invalid RSA-SHA256 webhook signature", "invalid_signature")

    # 2. Authoritative server-to-server check with Qi Card Sandbox
    authoritative_data = await qi_gateway.get_payment_status(str(payment_id))
    auth_status = (authoritative_data.get("status") or status_str).upper()

    # 3. Locate payment session idempotently
    stmt = select(PaymentSession).where(
        or_(
            PaymentSession.id == str(payment_id),
            PaymentSession.key == str(payment_id),
            PaymentSession.outcome == str(payment_id),
        )
    )
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        # Check by requestId
        req_id = payload.get("requestId")
        if req_id:
            stmt_req = select(PaymentSession).where(PaymentSession.id == str(req_id))
            session = (await db.execute(stmt_req)).scalar_one_or_none()

    if not session:
        return success_response({"received": True, "message": "Session not found or already processed"})

    if session.status == "success":
        return success_response({"received": True, "already_settled": True})

    if auth_status == "SUCCESS":
        # Verify currency and amount matches expected
        if amount is not None:
            expected_amount = Decimal(str(session.amount))
            received_amount = Decimal(str(amount))
            if received_amount < expected_amount:
                session.status = "partially_paid"
                await db.commit()
                return success_response({"received": True, "status": "partially_paid"})

        session.status = "success"
        session.settled_at = datetime.now(timezone.utc)
        if not session.outcome or session.outcome == "created":
            session.outcome = str(payment_id)

        # Retrieve actor for payment logging
        stmt_actor = select(Profile).where(Profile.id == session.user_id)
        actor = (await db.execute(stmt_actor)).scalar_one_or_none()
        if not actor:
            stmt_m = select(Profile).where(Profile.role == "manager")
            actor = (await db.execute(stmt_m)).scalars().first()

        from app.schemas.finance import PayRequest
        await finance_service.take_payment(
            db,
            session.appointment_id,
            PayRequest(amount=float(session.amount), currency=session.currency),
            "online",
            actor,
            ref_key=f"gateway:{session.id}",
        )

        # Clear pay_by on appointment
        stmt_appt = select(Appointment).where(Appointment.id == session.appointment_id)
        appt = (await db.execute(stmt_appt)).scalar_one_or_none()
        if appt:
            appt.pay_by = None

        # Emit transactional outbox event
        record_outbox_event(
            db=db,
            channel="public:queue",
            event_type="payment.settled",
            payload={
                "appointment_id": session.appointment_id,
                "amount": float(session.amount),
                "currency": session.currency,
                "status": "success",
            },
        )
        await db.commit()
    elif auth_status in ("FAILED", "DECLINED"):
        session.status = "failed"
        await db.commit()
    elif auth_status == "CANCELLED":
        session.status = "canceled"
        await db.commit()

    return success_response({"received": True, "status": session.status})
