from typing import Optional
from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.patient import FamilyInput
from app.schemas.clinical import RateVisitRequest
from app.schemas.auth import DeleteAccountRequest
from app.services import (
    patient_service,
    appointment_service,
    clinical_service,
    lab_service,
    admin_service,
    auth_service,
    payment_service,
)

router = APIRouter(prefix="/me", tags=["Patient Account & Records"])


@router.get("/family")
async def get_my_family(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    family = await patient_service.get_my_family(db, user)
    return success_response([f.model_dump() for f in family])


@router.post("/family")
async def add_family_member(
    req: FamilyInput,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    await patient_service.add_family_member(db, user, req)
    return success_response(None)


@router.put("/family/{member_id}")
async def update_family_member(
    member_id: int,
    req: FamilyInput,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    await patient_service.update_family_member(db, user, member_id, req)
    return success_response(None)


@router.delete("/family/{member_id}")
async def remove_family_member(
    member_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    await patient_service.remove_family_member(db, user, member_id)
    return success_response(None)


@router.get("/appointments")
async def get_my_appointments(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    appts = await appointment_service.get_my_appointments(db, user)
    return success_response([a.model_dump() for a in appts])


@router.get("/follow-ups")
async def get_my_follow_ups(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    follow_ups = await clinical_service.get_my_follow_ups(db, user)
    return success_response([f.model_dump() for f in follow_ups])


@router.get("/visits")
async def get_my_visits(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    visits = await clinical_service.get_my_visits(db, user)
    return success_response([v.model_dump() for v in visits])


@router.post("/visits/{visit_id}/rating")
async def rate_visit(
    visit_id: int,
    req: RateVisitRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    rating = await clinical_service.rate_visit(db, visit_id, req, user)
    return success_response(rating.model_dump())


@router.get("/results")
async def get_my_results(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    results = await lab_service.get_my_results(db, user)
    return success_response([r.model_dump() for r in results])


@router.get("/notifications")
async def get_my_notifications(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    notifications = await admin_service.get_my_notifications(db, user)
    return success_response([n.model_dump() for n in notifications])


@router.post("/notifications/read")
async def mark_notifications_read(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    await admin_service.mark_notifications_read(db, user)
    return success_response(None)


@router.get("/payments")
async def get_my_payments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    patient_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    history = await payment_service.get_patient_payment_history(
        db=db,
        user=user,
        limit=limit,
        offset=offset,
        patient_id=patient_id,
    )
    return success_response(history)


@router.delete("")
async def delete_my_account(
    req: DeleteAccountRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    await auth_service.delete_my_account(db, user, req.password)
    return success_response(None)
