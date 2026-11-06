from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.envelope import success_response
from app.services import doctor_service

router = APIRouter(prefix="/public", tags=["Public"])


@router.get("/doctors")
async def list_doctors(db: AsyncSession = Depends(get_db)):
    doctors = await doctor_service.list_public_doctors(db)
    return success_response([d.model_dump() for d in doctors])


@router.get("/queue-screen")
async def get_queue_screen(db: AsyncSession = Depends(get_db)):
    screens = await doctor_service.get_queue_screen(db)
    return success_response([s.model_dump() for s in screens])
