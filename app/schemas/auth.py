from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.common import Role


class UserSchema(BaseModel):
    id: int
    name: str
    phone: str
    role: Role
    doctor_id: Optional[int] = None


class LoginRequest(BaseModel):
    phone: str
    password: str


class RegisterRequest(LoginRequest):
    name: str = Field(..., min_length=2)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserSchema


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class DeleteAccountRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    phone: str


class ResetPasswordRequest(BaseModel):
    phone: str
    code: str
    new_password: str
