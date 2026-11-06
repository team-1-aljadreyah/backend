from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.services import finance_service

router = APIRouter(prefix="/ledger", tags=["General Ledger"])


@router.get("")
async def list_ledger(
    limit: Optional[int] = Query(None),
    offset: Optional[int] = Query(0),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("accountant", "manager")),
):
    ledger = await finance_service.list_ledger(db)
    total = len(ledger)
    if limit is not None:
        off = offset or 0
        items = ledger[off : off + limit]
    else:
        items = ledger
    return success_response({
        "items": [entry.model_dump() for entry in items],
        "total": total,
    })
