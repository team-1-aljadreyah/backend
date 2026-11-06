from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.schemas.pharmacy import DispenseRequest
from app.services import pharmacy_service

router = APIRouter(prefix="/prescriptions", tags=["Pharmacy Prescriptions"])


@router.get("")
async def list_prescriptions(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("pharmacy", "manager")),
):
    prescriptions = await pharmacy_service.list_prescriptions(db)
    return success_response([p.model_dump() for p in prescriptions])


@router.post("/{prescription_id}/dispense")
async def dispense(
    prescription_id: int,
    req: DispenseRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("pharmacy", "manager")),
):
    sale = await pharmacy_service.dispense_prescription(db, prescription_id, req, user)
    return success_response(sale.model_dump() if sale else None)
