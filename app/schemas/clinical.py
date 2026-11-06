from typing import List, Optional
from pydantic import BaseModel
from app.schemas.common import LabStatus
from app.schemas.doctor import DoctorSchema
from app.schemas.lab import LabResult
from app.schemas.service import ServiceSchema


class DoseInstructions(BaseModel):
    times_per_day: int
    timing: str  # "before_food" | "after_food" | "any"
    note: str


class Medicine(BaseModel):
    name: str
    dose: str
    days: int
    instructions: Optional[DoseInstructions] = None


class Vitals(BaseModel):
    systolic: Optional[float] = None
    diastolic: Optional[float] = None
    temperature: Optional[float] = None
    pulse: Optional[int] = None
    spo2: Optional[float] = None
    weight: Optional[float] = None
    height: Optional[float] = None


class VitalsRecord(Vitals):
    appointment_id: int
    at: str
    by: str


class VisitRating(BaseModel):
    stars: int
    comment: str
    at: str


class RateVisitRequest(BaseModel):
    stars: int
    comment: str


class PatientVisit(BaseModel):
    id: int
    created_at: str
    patient_name: str
    doctor: DoctorSchema
    diagnosis: str
    medicines: List[Medicine]


class MyVisit(PatientVisit):
    rating: Optional[VisitRating] = None


class VisitTest(BaseModel):
    id: int
    test: ServiceSchema
    status: LabStatus
    result: Optional[LabResult] = None


class DoctorVisit(PatientVisit):
    internal_note: str
    tests: List[VisitTest]
    follow_up_on: Optional[str] = None


class FollowUp(BaseModel):
    visit_id: int
    patient_id: int
    patient_name: str
    doctor: DoctorSchema
    due: str


class FinishVisitRequest(BaseModel):
    diagnosis: str
    internal_note: str
    medicines: List[Medicine]
    test_ids: List[int]
    procedure_ids: List[int]
    follow_up_days: Optional[int] = None


class FinishVisitResult(BaseModel):
    next_ticket: Optional[str] = None
