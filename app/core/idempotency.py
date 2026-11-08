import hashlib
import json
from typing import Any, Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models.governance import IdempotencyRecord
from app.core.exceptions import ConflictException


def compute_request_hash(data: Any) -> str:
    """
    Computes a canonical SHA-256 hash of the request payload or parameters.
    """
    if data is None:
        raw = ""
    elif isinstance(data, (dict, list)):
        raw = json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))
    elif hasattr(data, "model_dump"):
        raw = json.dumps(data.model_dump(), sort_keys=True, default=str, separators=(",", ":"))
    elif hasattr(data, "dict"):
        raw = json.dumps(data.dict(), sort_keys=True, default=str, separators=(",", ":"))
    else:
        raw = str(data)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def check_idempotency(
    db: AsyncSession,
    key: Optional[str],
    action: str,
    payload: Any,
    user_id: Optional[int] = None,
) -> Optional[Tuple[int, Any]]:
    """
    Checks if an idempotency key has already been processed.
    Returns (status_code, response_data) if already processed.
    Raises ConflictException if key was used with different payload or another user/action.
    Returns None if key is fresh.
    """
    if not key:
        return None

    stmt = select(IdempotencyRecord).where(IdempotencyRecord.key == key)
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()

    if not record:
        return None

    # Scope verification: Prevent cross-user / cross-action key hijacking
    if record.action != action:
        raise ConflictException(
            message="Idempotency key already used for a different operation",
            code="idempotency_conflict",
        )

    if user_id is not None and record.user_id is not None and record.user_id != user_id:
        raise ConflictException(
            message="Idempotency key already claimed by another user",
            code="idempotency_conflict",
        )

    req_hash = compute_request_hash(payload)
    if record.request_hash != req_hash:
        raise ConflictException(
            message="Idempotency key already used with different request parameters",
            code="idempotency_conflict",
        )

    return (record.response_status, record.response_data)


async def save_idempotency_record(
    db: AsyncSession,
    key: Optional[str],
    action: str,
    payload: Any,
    response_status: int,
    response_data: Any,
    user_id: Optional[int] = None,
) -> None:
    """
    Saves an idempotency record for subsequent idempotent replays.
    """
    if not key:
        return

    req_hash = compute_request_hash(payload)
    clean_data = response_data
    if hasattr(clean_data, "model_dump"):
        clean_data = clean_data.model_dump()

    record = IdempotencyRecord(
        key=key,
        user_id=user_id,
        action=action,
        request_hash=req_hash,
        response_status=response_status,
        response_data=clean_data,
    )
    db.add(record)
