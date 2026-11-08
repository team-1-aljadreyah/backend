import hashlib
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional
from fastapi import Request, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models.realtime import RateLimitEntry
from app.core.logging import logger


def ensure_utc(dt: Optional[datetime]) -> datetime:
    if not dt:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def check_rate_limit(
    db: AsyncSession,
    key_prefix: str,
    raw_identifier: str,
    max_requests: int = 10,
    window_seconds: int = 60,
) -> Tuple[bool, int, int]:
    """
    PostgreSQL-backed distributed rate limiter.
    Returns: (is_allowed: bool, remaining: int, retry_after_seconds: int)
    """
    key_material = f"{key_prefix}:{raw_identifier}".strip().lower()
    bucket_key = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    stmt = select(RateLimitEntry).where(RateLimitEntry.bucket_key == bucket_key).with_for_update()
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()

    if entry is None:
        expires_at = now + timedelta(seconds=window_seconds)
        new_entry = RateLimitEntry(
            bucket_key=bucket_key,
            counter=1,
            window_start=now,
            expires_at=expires_at,
        )
        db.add(new_entry)
        await db.flush()
        return True, max_requests - 1, 0

    # If window has expired, reset counter and window
    if ensure_utc(entry.expires_at) <= now:
        entry.counter = 1
        entry.window_start = now
        entry.expires_at = now + timedelta(seconds=window_seconds)
        await db.flush()
        return True, max_requests - 1, 0

    # Window still active
    if entry.counter >= max_requests:
        retry_after = max(1, int((ensure_utc(entry.expires_at) - now).total_seconds()))
        return False, 0, retry_after

    entry.counter += 1
    remaining = max(0, max_requests - entry.counter)
    await db.flush()
    return True, remaining, 0


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


async def enforce_rate_limit(
    db: AsyncSession,
    request: Request,
    action: str,
    max_requests: int = 10,
    window_seconds: int = 60,
    identifier: Optional[str] = None,
):
    ident = identifier or get_client_ip(request)
    allowed, remaining, retry_after = await check_rate_limit(
        db=db,
        key_prefix=action,
        raw_identifier=ident,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    if not allowed:
        logger.warning(f"Rate limit exceeded for {action}:{ident}. Retry after {retry_after}s.")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please wait {retry_after} seconds before trying again.",
            headers={"Retry-After": str(retry_after)},
        )
