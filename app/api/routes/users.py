from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.core.security import normalize_role
from app.database.models.profile import Profile
from app.schemas.admin import CreateStaffRequest, UpdateStaffRequest
from app.services import admin_service

router = APIRouter(prefix="/users", tags=["Staff Management"])


@router.get("")
async def list_staff(
    limit: Optional[int] = Query(None, description="Max number of items to return"),
    offset: Optional[int] = Query(0, description="Offset for pagination"),
    search: Optional[str] = Query(None, description="Search term matching staff name or phone"),
    role: Optional[str] = Query(None, description="Role/job filter (e.g. 'doctor', 'reception', 'doctors only')"),
    job: Optional[str] = Query(None, description="Alias for role filter"),
    role_filter: Optional[str] = Query(None, alias="roleFilter", description="Alias for role filter"),
    job_filter: Optional[str] = Query(None, alias="jobFilter", description="Alias for role filter"),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
):
    raw_role = role or job or role_filter or job_filter
    target_role = normalize_role(raw_role) if raw_role is not None else None

    # Frontend compatibility: when no parameters are provided (e.g. default useLoad(api.listStaff)),
    # return a plain array of StaffUser so unparameterized clients receive [...state.data] without throwing.
    if limit is None and search is None and raw_role is None and (offset is None or offset == 0):
        users = await admin_service.list_staff_users(db, user)
        return success_response([u.model_dump() for u in users])

    result = await admin_service.list_staff_users_paginated(
        db, user, limit=limit, offset=offset, search=search, role=target_role
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
