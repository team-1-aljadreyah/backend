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
    db: AsyncSession = Depends(get_db),
):
    payment_id = payload.get("paymentId") or payload.get("requestId")
    if payment_id:
        stmt_m = select(Profile).where(Profile.role == "manager")
        manager = (await db.execute(stmt_m)).scalars().first()
        if manager:
            try:
                await payment_service.get_payment_session(db, payment_id, manager)
            except Exception:
                pass
    return success_response({"received": True})
