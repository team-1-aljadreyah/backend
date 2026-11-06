from typing import Literal, Dict

Role = Literal["patient", "reception", "doctor", "pharmacy", "manager", "lab", "accountant"]
StaffRole = Literal["reception", "doctor", "pharmacy", "manager", "lab", "accountant"]
AppointmentStatus = Literal["booked", "arrived", "in_progress", "done", "cancelled", "no_show"]
BranchId = Literal["main", "second"]
Shift = Literal["morning", "evening"]
VisitKind = Literal["new", "followup"]
CancelReason = Literal["patient", "doctor_absent", "unpaid"]
Relation = Literal["self", "child", "parent", "spouse", "sibling", "other"]
BloodType = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
ServiceKind = Literal["test", "xray", "procedure"]
Currency = Literal["IQD", "USD"]
PaymentMethod = Literal["cash", "online"]
PaymentKind = Literal["payment", "refund", "reversal"]
SampleType = Literal["blood", "urine", "stool", "swab", "other"]
LabStatus = Literal["requested", "entered", "confirmed"]
StockLevel = Literal["ok", "low", "out"]
StockExpiry = Literal["ok", "soon", "expired", "none"]
StockMoveKind = Literal["create", "receive", "dispense", "edit", "sale"]
ExpenseCategory = Literal["rent", "salaries", "power", "supplies", "medicines", "maintenance", "other"]
InvoiceItemKind = Literal["visit", "service", "medicine", "discount"]
PaymentStatus = Literal["created", "success", "failed", "authentication_failed", "canceled"]
WelfareStatus = Literal["pending", "approved", "rejected"]
NotificationType = Literal[
    "doctor_absent",
    "doctor_late",
    "result_ready",
    "reminder",
    "turn_near",
    "booked",
    "rate_visit",
    "follow_up",
    "result_for_doctor",
    "welfare_submitted",
    "welfare_approved",
    "welfare_rejected",
]

Amounts = Dict[Currency, float]
