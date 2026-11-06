from datetime import date, datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin, PK_BIGINT


class Service(Base, TimestampMixin):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # test, xray, procedure
    price: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="IQD", nullable=False)
    template: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    lab_orders: Mapped[List["LabOrder"]] = relationship("LabOrder", back_populates="service")


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("patients.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("doctors.id"), nullable=False)
    appointment_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("appointments.id"), nullable=True)
    diagnosis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    internal_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    medicines: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    dispensed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    follow_up_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rating_stars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rating_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="visits")
    doctor: Mapped["Doctor"] = relationship("Doctor")
    appointment: Mapped[Optional["Appointment"]] = relationship("Appointment", back_populates="visit")
    lab_orders: Mapped[List["LabOrder"]] = relationship("LabOrder", back_populates="visit", cascade="all, delete-orphan")


class LabOrder(Base):
    __tablename__ = "lab_orders"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    visit_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("visits.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("patients.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("doctors.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("services.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="requested", nullable=False)  # requested, entered, confirmed
    result: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    history: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    visit: Mapped["Visit"] = relationship("Visit", back_populates="lab_orders")
    patient: Mapped["Patient"] = relationship("Patient")
    doctor: Mapped["Doctor"] = relationship("Doctor")
    service: Mapped["Service"] = relationship("Service", back_populates="lab_orders")
