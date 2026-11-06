from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.finance import CloseShiftRequest
from app.services import finance_service

router = APIRouter(prefix="/cash", tags=["Cash Management"])


@router.get("/shift")
async def get_shift_summary(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "accountant", "manager")),
):
    shift = await finance_service.get_shift_summary(db, user)
    return success_response(shift.model_dump())


@router.post("/closings")
async def close_shift(
    req: CloseShiftRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "manager")),
):
    closing = await finance_service.close_shift(db, req, user)
    return success_response(closing.model_dump())


@router.get("/closings")
async def list_closings(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "accountant", "manager")),
):
    closings = await finance_service.list_cash_closings(db, user)
    return success_response([c.model_dump() for c in closings])
