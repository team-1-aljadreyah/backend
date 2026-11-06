from typing import Optional, List, Callable
from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.connection import get_db
from app.database.models.profile import Profile
from app.core.security import decode_token
from app.core.exceptions import UnauthorizedException, ForbiddenException

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[Profile]:
    if not auth or not auth.credentials:
        return None

    token = auth.credentials
    payload = decode_token(token)
    if not payload:
        return None

    user_id_val = payload.get("sub") or payload.get("user_id")
    if not user_id_val:
        return None

    try:
        user_id = int(user_id_val)
    except (ValueError, TypeError):
        return None

    stmt = select(Profile).where(Profile.id == user_id, Profile.is_active == True)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    return profile


async def get_current_user(
    profile: Optional[Profile] = Depends(get_current_user_optional),
) -> Profile:
    if not profile:
        raise UnauthorizedException(message="Authentication required", code="unauthorized")
    return profile


def require_role(*roles: str) -> Callable:
    async def role_checker(current_user: Profile = Depends(get_current_user)) -> Profile:
        if roles and current_user.role not in roles:
            raise ForbiddenException(
                message=f"Access denied. Required role in {roles}, got '{current_user.role}'",
                code="forbidden",
            )
        return current_user

    return role_checker
