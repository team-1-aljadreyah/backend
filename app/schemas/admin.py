from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.common import Role, BranchId, Amounts, PaymentMethod, NotificationType
from app.schemas.finance import CountRow


class StaffUser(BaseModel):
    id: int
    name: str
    phone: str
    role: Role
    active: bool = True


class UpdateStaffRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    new_password: Optional[str] = None


class DoctorStaffInput(BaseModel):
    name_en: str
    specialty_ar: str
    specialty_en: str
    branch: BranchId
    fee: float


class CreateStaffRequest(BaseModel):
    name: str
    phone: str
    password: str
    role: Role
    doctor: Optional[DoctorStaffInput] = None


class ClinicSettingsSchema(BaseModel):
    cancel_hours: int
    no_show_limit: int
    deposit_amount: float
    prescription_days: int
    usd_rate: float
    welfare_discount_percent: float = 25.0


class AuditEntry(BaseModel):
    id: int
    at: str
    user_name: str
    role: Role
    action: str
    target: str


class ManagerOverview(BaseModel):
    appointments_today: int
    waiting_now: int
    visits_done_today: int
    doctors: int
    staff: int


class AnalyticsDay(BaseModel):
    date: str
    visits: int
    followups: int
    no_shows: int
    cancelled: int
    collected: float
    cash: float
    online: float


class DoctorAnalytics(BaseModel):
    label: str
    visits: int
    collected: float


class DoctorRatingSummary(BaseModel):
    label: str
    average: float
    count: int


class RecentRating(BaseModel):
    stars: int
    comment: str
    doctor: str
    at: str


class RatingsAnalytics(BaseModel):
    by_doctor: List[DoctorRatingSummary]
    recent: List[RecentRating]


class AnalyticsTotals(BaseModel):
    appointments: int
    visits: int
    no_shows: int
    cancelled: int
    walk_ins: int
    followups: int
    new_patients: int
    collected: Amounts


class AnalyticsSchema(BaseModel):
    from_date: str = Field(..., serialization_alias="from")
    to: str
    totals: AnalyticsTotals
    by_day: List[AnalyticsDay]
    by_doctor: List[DoctorAnalytics]
    by_hour: List[CountRow]
    by_method: Dict[PaymentMethod, float]
    top_diagnoses: List[CountRow]
    ratings: RatingsAnalytics


class AppNotification(BaseModel):
    id: int
    type: NotificationType
    params: Dict[str, Any]
    at: str
    read: bool
