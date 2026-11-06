from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.service import ServiceInput
from app.services import admin_service

router = APIRouter(prefix="/services", tags=["Clinic Services"])


@router.get("")
async def list_services(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    services = await admin_service.list_services(db)
    return success_response([s.model_dump() for s in services])


@router.post("")
async def create_service(
    req: ServiceInput,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    await admin_service.create_service(db, req, user)
    return success_response(None)


@router.put("/{service_id}")
async def update_service(
    service_id: int,
    req: ServiceInput,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    await admin_service.update_service(db, service_id, req, user)
    return success_response(None)
