from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models.governance import AuditLog
from app.database.models.profile import Profile


async def log_audit(
    db: AsyncSession,
    user: Profile,
    action: str,
    target: str,
):
    entry = AuditLog(
        at=datetime.now(timezone.utc),
        user_name=user.name,
        role=user.role,
        action=action,
        target=target,
    )
    db.add(entry)
