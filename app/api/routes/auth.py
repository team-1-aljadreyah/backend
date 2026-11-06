from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.core.envelope import success_response
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


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    res = await auth_service.login(db, req)
    return success_response(res.model_dump())


@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    res = await auth_service.register(db, req)
    return success_response(res.model_dump())


@router.post("/logout")
async def logout():
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
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
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
