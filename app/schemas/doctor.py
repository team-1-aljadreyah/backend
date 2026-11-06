from typing import List, Optional
from pydantic import BaseModel
from app.schemas.common import BranchId, Shift


class DoctorSchema(BaseModel):
    id: int
    name: str
    name_ar: str
    specialty: str
    specialty_ar: str
    fee: float
    new_minutes: int
    followup_minutes: int


class WorkDay(BaseModel):
    branch: BranchId
    shift: Shift


class DoctorDay(BaseModel):
    date: str
    work: Optional[WorkDay] = None
    absent: bool


class DoctorLate(BaseModel):
    date: str
    minutes: int


class DoctorSchedule(BaseModel):
    doctor: DoctorSchema
    clinic_percent: float
    service_percent: float
    days: List[Optional[WorkDay]]
    absences: List[str]
    late: Optional[DoctorLate] = None


class UpdateScheduleRequest(BaseModel):
    fee: float
    clinic_percent: float
    service_percent: float
    new_minutes: int
    followup_minutes: int
    days: List[Optional[WorkDay]]


class Slot(BaseModel):
    time: str
    available: bool


class ScreenDoctor(BaseModel):
    doctor: DoctorSchema
    branch: BranchId
    absent: bool
    late_minutes: int
    now: Optional[str] = None
    called_at: Optional[str] = None
    next: List[str]
    waiting: int
