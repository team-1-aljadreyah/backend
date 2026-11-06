from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, PK_BIGINT


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("appointments.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    label_ar: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="IQD", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="invoice_items")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("appointments.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="IQD", nullable=False)
    method: Mapped[str] = mapped_column(String(16), default="cash", nullable=False)  # cash, online
    kind: Mapped[str] = mapped_column(String(16), default="payment", nullable=False)  # payment, refund, reversal
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    by: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ref_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("payments.id"), nullable=True)
    key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)

    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="payments")


class CashClosing(Base):
    __tablename__ = "cash_closings"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    by: Mapped[str] = mapped_column(String(128), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    payments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_iqd: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0, nullable=False)
    expected_usd: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0, nullable=False)
    counted_iqd: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0, nullable=False)
    counted_usd: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0, nullable=False)
    difference_iqd: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0, nullable=False)
    difference_usd: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="IQD", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    by: Mapped[str] = mapped_column(String(128), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    voided_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PaymentSession(Base):
    __tablename__ = "payment_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    appointment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("appointments.id"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("profiles.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="IQD", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    form_url: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    return_url: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    outcome: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    appointment: Mapped["Appointment"] = relationship("Appointment")
    user: Mapped[Optional["Profile"]] = relationship("Profile")
