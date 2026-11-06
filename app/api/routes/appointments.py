from typing import Optional
from fastapi import APIRouter, Depends, Body, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.appointment import (
    BookRequest,
    StaffBookRequest,
    RescheduleRequest,
    WalkInRequest,
    CheckInRequest,
)
from app.schemas.clinical import Vitals, FinishVisitRequest
from app.schemas.finance import PayRequest
from app.services import appointment_service, clinical_service, finance_service

router = APIRouter(tags=["Appointments & Queues"])


@router.post("/appointments")
async def book(
    req: BookRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_idempotency_key_header: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    if not req.idempotency_key:
        req.idempotency_key = idempotency_key_header or x_idempotency_key_header
    res = await appointment_service.book_appointment(db, req, user)
    return success_response(res.model_dump())


@router.post("/appointments/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    await appointment_service.cancel_appointment(db, appointment_id, user)
    return success_response(None)


@router.post("/appointments/{appointment_id}/reschedule")
async def reschedule_appointment(
    appointment_id: int,
    req: RescheduleRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    await appointment_service.reschedule_appointment(db, appointment_id, req, user)
    return success_response(None)


@router.get("/appointments/booked-today")
async def list_booked_today(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
):
    booked = await appointment_service.list_booked_today(db)
    return success_response([b.model_dump() for b in booked])


@router.get("/appointments/upcoming")
async def list_upcoming(
    days: int = Query(7, ge=1, le=60),
    doctor_id: Optional[int] = Query(None),
    include_today: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager", "doctor")),
):
    appts = await appointment_service.get_upcoming_appointments(db, days, doctor_id, include_today, user)
    return success_response([a.model_dump() for a in appts])


@router.post("/appointments/by-staff")
async def staff_book(
    req: StaffBookRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_idempotency_key_header: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    if not req.idempotency_key:
        req.idempotency_key = idempotency_key_header or x_idempotency_key_header
    res = await appointment_service.staff_book_appointment(db, req, user)
    return success_response(res.model_dump())


@router.post("/appointments/{appointment_id}/check-in")
async def check_in(
    appointment_id: int,
    req: CheckInRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_idempotency_key_header: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    if not req.idempotency_key:
        req.idempotency_key = idempotency_key_header or x_idempotency_key_header
    await appointment_service.check_in_appointment(db, appointment_id, req.emergency, user, req.idempotency_key)
    return success_response(None)


@router.post("/walk-ins")
async def add_walk_in(
    req: WalkInRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_idempotency_key_header: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    if not req.idempotency_key:
        req.idempotency_key = idempotency_key_header or x_idempotency_key_header
    res = await appointment_service.add_walk_in(db, req, user)
    return success_response(res.model_dump())


@router.post("/appointments/{appointment_id}/start")
async def start_visit(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("doctor", "manager")),
):
    await clinical_service.start_visit(db, appointment_id, user)
    return success_response(None)


@router.put("/appointments/{appointment_id}/vitals")
async def save_vitals(
    appointment_id: int,
    req: Vitals,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "doctor", "manager")),
):
    record = await clinical_service.save_vitals(db, appointment_id, req, user)
    return success_response(record.model_dump())


@router.post("/appointments/{appointment_id}/finish")
async def finish_visit(
    appointment_id: int,
    req: FinishVisitRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("doctor", "manager")),
):
    result = await clinical_service.finish_visit(db, appointment_id, req, user)
    return success_response(result.model_dump())


@router.post("/appointments/{appointment_id}/no-show")
async def mark_no_show(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
):
    await appointment_service.mark_no_show(db, appointment_id, user)
    return success_response(None)


@router.post("/appointments/{appointment_id}/pay-cash")
async def pay_cash(
    appointment_id: int,
    req: PayRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_idempotency_key_header: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    if not req.idempotency_key:
        req.idempotency_key = idempotency_key_header or x_idempotency_key_header
    await finance_service.take_payment(db, appointment_id, req, "cash", user)
    return success_response(None)
