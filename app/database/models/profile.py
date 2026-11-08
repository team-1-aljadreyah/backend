from datetime import date, datetime, timezone
from typing import List, Optional, Any
from uuid import UUID
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, String, Text, JSON, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin, PK_BIGINT


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class Doctor(Base, TimestampMixin):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(128), nullable=False)
    specialty: Mapped[str] = mapped_column(String(128), nullable=False)
    specialty_ar: Mapped[str] = mapped_column(String(128), nullable=False)
    fee: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    new_minutes: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    followup_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    clinic_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=30.0, nullable=False)
    service_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=30.0, nullable=False)
    days: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    absences: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    late_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    profiles: Mapped[List["Profile"]] = relationship("Profile", back_populates="doctor")


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    auth_user_id: Mapped[Optional[UUID]] = mapped_column(Uuid, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="patient", nullable=False)
    doctor_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("doctors.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    doctor: Mapped[Optional["Doctor"]] = relationship("Doctor", back_populates="profiles")
    patients: Mapped[List["Patient"]] = relationship("Patient", back_populates="account")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_info: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["Profile"] = relationship("Profile")


class PasswordResetOTP(Base):
    __tablename__ = "password_reset_otps"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    otp_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cooldown_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
