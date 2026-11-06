from typing import List, Optional
from pydantic import BaseModel
from app.schemas.common import (
    Currency,
    Amounts,
    PaymentMethod,
    PaymentKind,
    ExpenseCategory,
    AppointmentStatus,
    PaymentStatus,
)


class MoneySummary(BaseModel):
    total: Amounts
    paid: Amounts
    balance: Amounts


class InvoiceItemSchema(BaseModel):
    id: int
    label: str
    label_ar: str
    kind: str
    price: float
    currency: Currency


class Payment(BaseModel):
    id: int
    amount: float
    currency: Currency
    method: PaymentMethod
    kind: PaymentKind
    at: str
    by: str
    reason: str


class Invoice(BaseModel):
    appointment_id: int
    patient_name: str
    doctor_name: str
    date: str
    time: str
    status: AppointmentStatus
    items: List[InvoiceItemSchema]
    payments: List[Payment]
    money: MoneySummary


class PayRequest(BaseModel):
    amount: float
    currency: Currency
    idempotency_key: Optional[str] = None


class ShiftSummary(BaseModel):
    opened_at: str
    payments: int
    expected: Amounts


class CashClosingSchema(BaseModel):
    id: int
    by: str
    opened_at: str
    closed_at: str
    payments: int
    expected: Amounts
    counted: Amounts
    difference: Amounts
    note: str


class CloseShiftRequest(BaseModel):
    counted: Amounts
    note: str


class ExpenseVoid(BaseModel):
    by: str
    at: str
    reason: str


class ExpenseSchema(BaseModel):
    id: int
    date: str
    category: ExpenseCategory
    amount: float
    currency: Currency
    note: str
    by: str
    at: str
    voided: Optional[ExpenseVoid] = None


class ExpenseInput(BaseModel):
    date: str
    category: ExpenseCategory
    amount: float
    currency: Currency
    note: str


class LedgerEntry(Payment):
    appointment_id: int
    patient_name: str
    doctor_name: str
    reversible: bool


class DoctorDues(BaseModel):
    doctor_id: int
    doctor_name: str
    visits: int
    visit_income: float
    procedure_income: float
    doctor_share: float
    clinic_share: float


class CountRow(BaseModel):
    label: str
    count: int


class Report(BaseModel):
    month: str
    by_day: List[CountRow]
    by_doctor: List[CountRow]
    by_branch: List[CountRow]
    top_no_shows: List[CountRow]
    billed: Amounts
    collected: Amounts
    today_billed: Amounts
    today_collected: Amounts
    pharmacy_month: float
    pharmacy_today: float
    expenses: Amounts
    profit: Amounts


class PaymentSessionSchema(BaseModel):
    payment_id: str
    appointment_id: int
    amount: float
    currency: Currency = "IQD"
    status: PaymentStatus
    form_url: str
    created_at: str
    pay_by: Optional[str] = None


class StartPaymentRequest(BaseModel):
    idempotency_key: Optional[str] = None
    return_url: str = ""


class PaymentLogEntry(BaseModel):
    id: str
    kind: str  # PaymentKind | "attempt"
    status: Optional[PaymentStatus] = None
    at: str
    amount: float
    currency: Currency
    method: PaymentMethod
    receipt_no: Optional[int] = None
    by: str
    reason: str
    appointment_id: int
    patient_name: str
    doctor_name: str
    appointment_date: str
    appointment_time: str


class PaginatedPaymentLog(BaseModel):
    items: List[PaymentLogEntry]
    total: int
