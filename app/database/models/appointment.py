from datetime import date, datetime, timezone
from typing import List, Optional
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, String, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin, PK_BIGINT


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"
    __table_args__ = (
        Index(
            "idx_unique_doctor_active_slot",
            "doctor_id",
            "date",
            "time",
            unique=True,
            sqlite_where=text("status IN ('booked', 'arrived', 'in_progress', 'done') AND time != ''"),
            postgresql_where=text("status IN ('booked', 'arrived', 'in_progress', 'done') AND time != ''"),
        ),
    )

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("patients.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("doctors.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    time: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default="new", nullable=False)
    branch: Mapped[str] = mapped_column(String(16), default="main", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="booked", nullable=False)
    emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    arrival_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ticket: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    called_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    pay_by: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship("Doctor")
    vitals: Mapped[Optional["AppointmentVitals"]] = relationship("AppointmentVitals", back_populates="appointment", uselist=False)
    invoice_items: Mapped[List["InvoiceItem"]] = relationship("InvoiceItem", back_populates="appointment", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="appointment")
    visit: Mapped[Optional["Visit"]] = relationship("Visit", back_populates="appointment", uselist=False)
