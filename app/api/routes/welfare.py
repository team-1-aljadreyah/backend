from typing import List, Optional
from fastapi import APIRouter, Depends, Form, File, UploadFile, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.welfare import WelfareRequestSchema, WelfareReviewRequest
from app.schemas.common import WelfareStatus
from app.services import welfare_service

router = APIRouter(tags=["Social Welfare"])


@router.get("/me/welfare")
async def get_my_welfare(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    items = await welfare_service.get_family_welfare(db, user)
    return success_response([i.model_dump() for i in items])


@router.post("/patients/{patient_id}/welfare")
async def submit_welfare(
    patient_id: int,
    card_number: str = Form(...),
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    res = await welfare_service.submit_welfare(
        db=db,
        patient_id=patient_id,
        card_number=card_number,
        photo=photo,
        user=user,
    )
    return success_response(res.model_dump())


@router.get("/welfare")
async def list_welfare(
    status: WelfareStatus = Query("pending"),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
):
    items = await welfare_service.list_welfare(db, status)
    return success_response([i.model_dump() for i in items])


@router.post("/welfare/{request_id}/review")
async def review_welfare(
    request_id: int,
    req: WelfareReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
):
    res = await welfare_service.review_welfare(db, request_id, req, user)
    return success_response(res.model_dump())
