from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import get_current_user, get_current_user_optional
from app.core.envelope import success_response
from app.core.rate_limiter import enforce_rate_limit, get_client_ip
from app.database.models.profile import Profile
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RefreshTokenRequest,
    DeleteAccountRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserSchema,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


@router.post("/login")
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(db, request, action="auth.login", max_requests=20, window_seconds=60)
    res = await auth_service.login(db, req)
    return success_response(res.model_dump())


@router.post("/register")
async def register(req: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(db, request, action="auth.register", max_requests=10, window_seconds=300)
    res = await auth_service.register(db, req)
    return success_response(res.model_dump())


@router.post("/logout")
async def logout(
    req: Optional[LogoutRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Profile] = Depends(get_current_user_optional),
):
    if current_user:
        await auth_service.logout(db, current_user, req.refresh_token if req else None)
    return success_response(None)


@router.post("/refresh")
async def refresh_tokens(req: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    res = await auth_service.refresh_tokens(db, req.refresh_token)
    return success_response(res.model_dump())


@router.post("/password/change")
async def change_password(
    req: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    await auth_service.change_password(db, current_user, req.current_password, req.new_password)
    return success_response(None)


@router.post("/password/forgot")
@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(db, request, action="auth.forgot_password", max_requests=5, window_seconds=300, identifier=req.phone)
    res = await auth_service.forgot_password(db, req.phone)
    return success_response(res)


@router.post("/password/reset")
@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.reset_password(db, req.phone, req.code, req.new_password)
    return success_response(None)


@router.get("/me")
async def get_me(current_user: Profile = Depends(get_current_user)):
    user_data = UserSchema(
        id=current_user.id,
        name=current_user.name,
        phone=current_user.phone,
        role=current_user.role,
        doctor_id=current_user.doctor_id,
    )
    return success_response(user_data.model_dump())
