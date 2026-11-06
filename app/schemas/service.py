from typing import List, Optional
from pydantic import BaseModel
from app.schemas.common import ServiceKind, Currency


class ResultTemplateRow(BaseModel):
    name: str
    unit: str
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None


class ServiceSchema(BaseModel):
    id: int
    name: str
    name_ar: str
    kind: ServiceKind
    price: float
    currency: Currency
    template: Optional[List[ResultTemplateRow]] = None


class ServiceInput(BaseModel):
    name: str
    name_ar: str
    kind: ServiceKind
    price: float
    currency: Currency
