from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.services import finance_service

router = APIRouter(prefix="/invoices", tags=["Invoicing"])


@router.get("/today")
async def get_today_invoices(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("reception", "accountant", "manager")),
):
    invoices = await finance_service.get_today_invoices(db)
    return success_response([i.model_dump() for i in invoices])
