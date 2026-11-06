from datetime import date, datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin, PK_BIGINT


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    normalized_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    account_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("profiles.id"), nullable=True)
    relation: Mapped[str] = mapped_column(String(32), default="self", nullable=False)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    allergies: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    conditions: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    blood_type: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    merged_into_patient_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True)
    merged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    merged_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    merge_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    account: Mapped[Optional["Profile"]] = relationship("Profile", back_populates="patients")
    appointments: Mapped[List["Appointment"]] = relationship("Appointment", back_populates="patient")
    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="patient")
    welfare_requests: Mapped[List["WelfareRequest"]] = relationship("WelfareRequest", back_populates="patient")
    merged_into: Mapped[Optional["Patient"]] = relationship("Patient", remote_side=[id], foreign_keys=[merged_into_patient_id])


class PatientMerge(Base):
    __tablename__ = "patient_merges"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    source_patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    target_patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    merged_by_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id"), nullable=False)
    merged_by_name: Mapped[str] = mapped_column(String(128), nullable=False)
    merge_reason: Mapped[str] = mapped_column(Text, nullable=False)
    records_transferred: Mapped[Any] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    source_patient: Mapped["Patient"] = relationship("Patient", foreign_keys=[source_patient_id])
    target_patient: Mapped["Patient"] = relationship("Patient", foreign_keys=[target_patient_id])
    merged_by_profile: Mapped["Profile"] = relationship("Profile")


class AppointmentVitals(Base):
    __tablename__ = "appointment_vitals"

    appointment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("appointments.id"), primary_key=True)
    patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("patients.id"), nullable=False)
    systolic: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    diastolic: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Numeric(4, 1), nullable=True)
    pulse: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spo2: Mapped[Optional[float]] = mapped_column(Numeric(4, 1), nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    height: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    by: Mapped[str] = mapped_column(String(128), nullable=False)

    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="vitals")


class WelfareRequest(Base):
    __tablename__ = "welfare_requests"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("patients.id"), nullable=False)
    patient_name: Mapped[str] = mapped_column(String(128), nullable=False)
    patient_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    card_number: Mapped[str] = mapped_column(String(64), nullable=False)
    photo_url: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reject_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="welfare_requests")
