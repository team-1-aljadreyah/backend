from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from app.schemas.common import BloodType, Relation, AppointmentStatus, VisitKind, CancelReason, BranchId
from app.schemas.clinical import Medicine, VisitTest
from app.schemas.finance import MoneySummary, Payment, PaymentLogEntry
from app.schemas.welfare import WelfareRequestSchema


class MedicalAlerts(BaseModel):
    allergies: List[str]
    conditions: List[str]
    blood_type: Optional[BloodType] = None


class FamilyMember(BaseModel):
    id: int
    name: str
    relation: Relation
    birth_date: Optional[str] = None
    phone: Optional[str] = None
    alerts: MedicalAlerts


class FamilyInput(BaseModel):
    name: str
    relation: Relation
    birth_date: Optional[str] = None
    phone: Optional[str] = None


class BookingRules(BaseModel):
    no_shows: int
    deposit_required: bool
    deposit_amount: float
    welfare_percent: int = 0


class PatientSummary(BaseModel):
    id: int
    name: str
    phone: str
    has_account: bool
    relation: Optional[Relation] = None
    appointments: int
    visits: int
    no_shows: int
    last_visit: Optional[str] = None
    merged_into_patient_id: Optional[int] = None
    is_merged: bool = False


class PatientAppointment(BaseModel):
    id: int
    doctor_name: str
    date: str
    time: str
    kind: VisitKind
    branch: BranchId
    status: AppointmentStatus
    emergency: bool
    cancel_reason: Optional[CancelReason] = None
    pay_by: Optional[str] = None
    money: MoneySummary


class PatientFileVisit(BaseModel):
    id: int
    created_at: str
    doctor_name: str
    diagnosis: str
    medicines: List[Medicine]
    dispensed: bool
    tests: List[VisitTest]


class PatientPayment(Payment):
    appointment_id: int


class PatientFile(BaseModel):
    patient: PatientSummary
    alerts: MedicalAlerts
    family: List[FamilyMember]
    appointments: List[PatientAppointment]
    visits: List[PatientFileVisit]
    payments: List[PatientPayment]
    money: MoneySummary
    payment_log: Optional[List[PaymentLogEntry]] = None
    welfare: Optional[WelfareRequestSchema] = None


class DuplicateCheckRequest(BaseModel):
    name: str
    phone: str
    birth_date: Optional[str] = None


class DuplicateCandidate(BaseModel):
    patient: PatientSummary
    confidence: float
    match_type: str
    reasons: List[str]


class DuplicateCheckResult(BaseModel):
    candidates: List[DuplicateCandidate]
    has_exact_match: bool


class DuplicateGroup(BaseModel):
    group_id: str
    match_type: str
    patients: List[PatientSummary]


class PatientMergeRequest(BaseModel):
    primary_patient_id: int
    source_patient_id: int
    reason: str


class PatientMergeResult(BaseModel):
    primary_patient: PatientSummary
    source_patient_id: int
    records_transferred: Dict[str, int]
    merged_at: str
    merged_by: str
