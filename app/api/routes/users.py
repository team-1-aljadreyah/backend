from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.admin import CreateStaffRequest, UpdateStaffRequest
from app.services import admin_service

router = APIRouter(prefix="/users", tags=["Staff Management"])


@router.get("")
async def list_staff(
    limit: Optional[int] = Query(None),
    offset: Optional[int] = Query(0),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
):
    result = await admin_service.list_staff_users_paginated(
        db, user, limit=limit, offset=offset, search=search
    )
    return success_response(result)


@router.post("")
async def create_staff(
    req: CreateStaffRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
):
    await admin_service.create_staff_user(db, req, user)
    return success_response(None)


@router.patch("/{user_id}")
async def update_staff(
    user_id: int,
    req: UpdateStaffRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    await admin_service.update_staff_user(db, user_id, req, user)
    return success_response(None)


@router.post("/{user_id}/enable")
async def enable_staff(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    await admin_service.set_staff_active(db, user_id, True, user)
    return success_response(None)


@router.post("/{user_id}/disable")
async def disable_staff(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    await admin_service.set_staff_active(db, user_id, False, user)
    return success_response(None)
