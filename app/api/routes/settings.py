from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.admin import ClinicSettingsSchema
from app.services import admin_service

router = APIRouter(prefix="/settings", tags=["Clinic Settings"])


@router.get("")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    settings = await admin_service.get_clinic_settings(db)
    return success_response(settings.model_dump())


@router.put("")
async def update_settings(
    req: ClinicSettingsSchema,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    updated = await admin_service.update_clinic_settings(db, req, user)
    return success_response(updated.model_dump())
