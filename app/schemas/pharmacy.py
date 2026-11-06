from typing import List, Optional, Literal
from pydantic import BaseModel
from app.schemas.common import StockLevel, StockExpiry, StockMoveKind
from app.schemas.clinical import DoseInstructions, Medicine


class StockItemSchema(BaseModel):
    id: int
    name: str
    unit: str
    quantity: int
    low_level: int
    expires_on: Optional[str] = None
    barcode: Optional[str] = None
    price: float
    level: StockLevel
    expiry: StockExpiry


class StockInput(BaseModel):
    name: str
    price: float
    unit: str
    quantity: int
    low_level: int
    expires_on: Optional[str] = None
    barcode: Optional[str] = None


class ReceiveStockRequest(BaseModel):
    quantity: int
    expires_on: Optional[str] = None
    idempotency_key: Optional[str] = None


class SaleLine(BaseModel):
    stock_id: int
    name: str
    unit: str
    quantity: int
    unit_price: float
    total: float


class PharmacySaleSchema(BaseModel):
    id: int
    at: str
    by: str
    kind: Literal["prescription", "counter"]
    customer: str
    lines: List[SaleLine]
    total: float


class CounterSaleLine(BaseModel):
    stock_id: int
    quantity: int


class CounterSaleRequest(BaseModel):
    customer: str
    lines: List[CounterSaleLine]
    idempotency_key: Optional[str] = None


class StockMoveSchema(BaseModel):
    id: int
    at: str
    by: str
    kind: StockMoveKind
    stock_id: int
    item_name: str
    unit: str
    change: int
    quantity_after: int
    note: str


class CatalogMedicine(BaseModel):
    name: str
    availability: Literal["available", "low", "out", "expired"]


class DispenseLine(BaseModel):
    stock_id: Optional[int] = None
    quantity: int
    instructions: DoseInstructions


class DispenseRequest(BaseModel):
    lines: List[DispenseLine]


class PrescriptionSchema(BaseModel):
    id: int
    patient_name: str
    allergies: List[str]
    medicines: List[Medicine]
    dispensed: bool
    created_at: str
    expires_at: str
    expired: bool
