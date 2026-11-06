from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.services import finance_service

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/doctor-dues")
async def get_doctor_dues(
    month: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("accountant", "manager")),
):
    target_month = month or datetime.now().strftime("%Y-%m")
    dues = await finance_service.get_doctor_dues(db, target_month)
    return success_response([d.model_dump() for d in dues])


@router.get("/summary")
async def get_report_summary(
    month: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("accountant", "manager")),
):
    target_month = month or datetime.now().strftime("%Y-%m")
    rep = await finance_service.get_report_summary(db, target_month)
    return success_response(rep.model_dump())
