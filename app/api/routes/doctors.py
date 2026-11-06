from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import get_current_user, get_current_user_optional, require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.doctor import UpdateScheduleRequest
from app.services import doctor_service, appointment_service

router = APIRouter(prefix="/doctors", tags=["Doctors & Schedules"])


@router.get("/schedules")
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager", "reception")),
):
    schedules = await doctor_service.list_doctor_schedules(db)
    return success_response([s.model_dump() for s in schedules])


@router.get("/{doctor_id}/days")
async def get_doctor_days(
    doctor_id: int,
    db: AsyncSession = Depends(get_db),
    user: Optional[Profile] = Depends(get_current_user_optional),
):
    days = await doctor_service.get_doctor_days(db, doctor_id)
    return success_response([d.model_dump() for d in days])


@router.get("/{doctor_id}/slots")
async def get_doctor_slots(
    doctor_id: int,
    date: str = Query(...),
    kind: str = Query("new"),
    db: AsyncSession = Depends(get_db),
    user: Optional[Profile] = Depends(get_current_user_optional),
):
    slots = await doctor_service.get_doctor_slots(db, doctor_id, date, kind)
    return success_response([s.model_dump() for s in slots])


@router.put("/{doctor_id}/schedule")
async def update_schedule(
    doctor_id: int,
    req: UpdateScheduleRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    await doctor_service.update_schedule(db, doctor_id, req, user)
    return success_response(None)


@router.post("/{doctor_id}/absences")
async def mark_absent(
    doctor_id: int,
    date: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    cancelled = await doctor_service.mark_doctor_absent(db, doctor_id, date, user)
    return success_response({"cancelled": cancelled})


@router.post("/{doctor_id}/late")
async def mark_late(
    doctor_id: int,
    minutes: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager", "reception")),
):
    notified = await doctor_service.mark_doctor_late(db, doctor_id, minutes, user)
    return success_response({"notified": notified})


@router.get("/{doctor_id}/queue")
async def get_doctor_queue(
    doctor_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("doctor", "reception", "manager")),
):
    queue = await appointment_service.get_doctor_queue(db, doctor_id, user)
    return success_response([q.model_dump() for q in queue])
