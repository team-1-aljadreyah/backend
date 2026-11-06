from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import require_role
from app.core.envelope import success_response
from app.database.models.profile import Profile
from app.services import admin_service

router = APIRouter(prefix="/audit", tags=["Audit Log"])


@router.get("")
async def list_audit(
    action: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    offset: Optional[int] = Query(0),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_role("manager")),
):
    entries = await admin_service.list_audit_logs(db, action=action)
    total = len(entries)
    if limit is not None:
        off = offset or 0
        items = entries[off : off + limit]
    else:
        items = entries
    return success_response({
        "items": [e.model_dump() for e in items],
        "total": total,
    })
