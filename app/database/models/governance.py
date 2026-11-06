from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, PK_BIGINT


class ClinicSettings(Base):
    __tablename__ = "clinic_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    cancel_hours: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    no_show_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    deposit_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=10000.0, nullable=False)
    prescription_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    usd_rate: Mapped[float] = mapped_column(Numeric(10, 2), default=1310.0, nullable=False)
    welfare_discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=25.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(256), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id"), nullable=False)
    key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    params: Mapped[Any] = mapped_column(JSON, default=dict, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["Profile"] = relationship("Profile", back_populates="notifications")


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_data: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
