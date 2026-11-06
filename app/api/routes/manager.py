from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.services import admin_service

router = APIRouter(prefix="/manager", tags=["Manager Operations"])


@router.get("/overview")
async def get_manager_overview(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    overview = await admin_service.get_manager_overview(db)
    return success_response(overview.model_dump())


@router.get("/analytics")
async def get_analytics(
    days: int = Query(7),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    analytics = await admin_service.get_analytics(db, days)
    return success_response(analytics.model_dump(by_alias=True))
