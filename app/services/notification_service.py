from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models.governance import Notification
from app.database.models.patient import Patient
from app.database.models.profile import Profile
from app.services.realtime_service import record_outbox_event


async def notify_user(
    db: AsyncSession,
    user_id: int,
    key: str,
    notification_type: str,
    params: Dict[str, Any],
):
    # Check if duplicate notification key already exists
    stmt = select(Notification).where(Notification.key == key)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        return

    item = Notification(
        user_id=user_id,
        key=key,
        type=notification_type,
        params=params,
        at=datetime.now(timezone.utc),
        read=False,
    )
    db.add(item)

    # Publish transactional outbox event for user-specific real-time delivery
    record_outbox_event(
        db=db,
        channel=f"user:{user_id}",
        event_type="notification.created",
        payload={
            "user_id": user_id,
            "type": notification_type,
            "params": params,
        },
    )


async def notify_patient(
    db: AsyncSession,
    patient_id: int,
    key: str,
    notification_type: str,
    params: Dict[str, Any],
):
    stmt = select(Patient.account_id).where(Patient.id == patient_id)
    res = await db.execute(stmt)
    account_id = res.scalar_one_or_none()
    if account_id:
        await notify_user(db, account_id, key, notification_type, params)


async def notify_role(
    db: AsyncSession,
    role: str,
    key_prefix: str,
    notification_type: str,
    params: Dict[str, Any],
):
    stmt = select(Profile.id).where(Profile.role == role, Profile.is_active == True)
    user_ids = (await db.execute(stmt)).scalars().all()
    for uid in user_ids:
        await notify_user(db, uid, f"{key_prefix}:{uid}", notification_type, params)
