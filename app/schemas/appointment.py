from typing import Optional, Literal
from pydantic import BaseModel
from app.schemas.common import VisitKind, BranchId, AppointmentStatus, CancelReason
from app.schemas.doctor import DoctorSchema
from app.schemas.finance import MoneySummary, PaymentSessionSchema

PayChoice = Literal["none", "clinic", "deposit", "full"]


class BookRequest(BaseModel):
    patient_id: int
    doctor_id: int
    date: str
    time: str
    kind: VisitKind
    pay: PayChoice = "none"
    idempotency_key: Optional[str] = None
    return_url: Optional[str] = ""


class BookResult(BaseModel):
    appointment_id: int
    payment: Optional[PaymentSessionSchema] = None


class NewPatientInput(BaseModel):
    name: str
    phone: str


class StaffBookRequest(BaseModel):
    patient_id: Optional[int] = None
    new_patient: Optional[NewPatientInput] = None
    doctor_id: int
    date: str
    time: str
    kind: VisitKind
    idempotency_key: Optional[str] = None


class StaffBookResult(BaseModel):
    patient_id: int


class RescheduleRequest(BaseModel):
    date: str
    time: str


class MyAppointment(BaseModel):
    id: int
    patient_name: str
    doctor: DoctorSchema
    date: str
    time: str
    kind: VisitKind
    branch: BranchId
    status: AppointmentStatus
    ahead: Optional[int] = None
    can_change: bool
    cancel_reason: Optional[CancelReason] = None
    late_minutes: int
    ticket: Optional[str] = None
    pay_by: Optional[str] = None
    money: MoneySummary


class StaffAppointment(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    doctor_id: int
    date: str
    time: str
    kind: VisitKind
    branch: BranchId
    status: AppointmentStatus
    emergency: bool
    ticket: Optional[str] = None
    has_vitals: bool
    pay_by: Optional[str] = None


class WalkInRequest(BaseModel):
    name: str
    phone: str
    doctor_id: int
    emergency: bool
    idempotency_key: Optional[str] = None


class WalkInResult(BaseModel):
    duplicate: bool


class CheckInRequest(BaseModel):
    emergency: bool = False
    idempotency_key: Optional[str] = None
