from typing import Optional, Literal
from pydantic import BaseModel
from app.schemas.common import WelfareStatus


class WelfareRequestSchema(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_phone: str
    card_number: str
    photo_url: str
    status: WelfareStatus
    submitted_at: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    valid_until: Optional[str] = None
    reject_reason: str = ""


class WelfareReviewRequest(BaseModel):
    approve: bool
    valid_until: Optional[str] = None
    reason: Optional[str] = None
