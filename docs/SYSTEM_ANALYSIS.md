# SYSTEM ANALYSIS & ARCHITECTURAL SPECIFICATION
## Al-Jadreyah Clinic Management System Backend

---

## 1. Executive Summary & System Overview

The **Al-Jadreyah Clinic Management System** is an enterprise-grade healthcare management solution designed for multi-branch ambulatory medical centers. The frontend is built on **Next.js 15 (App Router)**, **TypeScript**, **Tailwind CSS**, and **Axios**, providing responsive, bilingual (Arabic & English, with full RTL/LTR support) interfaces for seven distinct user roles:

1. **Patient (مريض)**
2. **Receptionist (موظف استقبال)**
3. **Doctor (طبيب)**
4. **Pharmacist (صيدلي)**
5. **Laboratory Technician (فني مختبر)**
6. **Accountant (محاسب)**
7. **Clinic Manager (مدير المجمع)**

The backend architecture is engineered in **Python 3.12+** using **FastAPI**, **Pydantic v2**, and **SQLAlchemy 2.0 (async)** with **Supabase PostgreSQL** as the persistent relational database, **Supabase Auth** for identity management, and **Supabase Storage** for private clinical document storage.

---

## 2. Module Descriptions & Functional Scope

### 2.1 Authentication & Profile Identity
- **Phone & Password Authentication:** Primary Iraqi mobile format (`07XXXXXXXXX` locally, normalized to E.164 `+9647XXXXXXXXX` for identity services).
- **Session & Token Management:** JWT access tokens and long-lived refresh tokens.
- **Role Assignment:** Public self-registration defaults strictly to the `patient` role. Administrative roles (`reception`, `doctor`, `pharmacy`, `lab`, `accountant`, `manager`) are created by authorized staff/managers only.
- **Account Disassociation:** Account deletion preserves clinical patient files and audit trails while purging authentication credentials and unlinking active session bindings.

### 2.2 Patient & Family Unit Management
- **Primary Patient File:** Links an internal integer identifier, full legal name, phone number, and optional associated user account ID.
- **Family Accounts:** Account holders can add family members (`child`, `parent`, `spouse`, `sibling`, `other`) who may lack personal phone numbers or exact birth dates.
- **Medical Alerts & Allergies:** Immediate clinical flags (substance allergies like Penicillin/Aspirin, chronic conditions like hypertension/diabetes, and ABO/Rh blood groups) displayed across all treatment touchpoints.

### 2.3 Doctor Schedules & Capacity Planning
- **Multi-Branch Operations:** Branch identification (`main`, `second`).
- **Weekly Working Schedules:** 7-day schedule array (Sunday to Saturday) mapping to shifts (`morning`: 09:00–13:00, `evening`: 16:00–20:00) or scheduled off days.
- **Dynamic Slot Generation:** Calculated using doctor-specific consultation durations (`new_minutes`, `followup_minutes`), filtering past time slots, doctor absences, and active overlapping bookings.
- **Absence & Delay Handling:** Absence registration automatically cancels upcoming bookings with refund triggers and broadcasts patient notifications. Late notifications inform queue participants in real time.

### 2.4 Appointment Booking & Waiting Queue
- **Online Patient Booking:** Slot validation, visit kind selection (`new` vs. `followup`), deposit requirements check, and payment choices (`clinic`, `deposit`, `full`).
- **Staff Assisted Booking:** Reception booking by phone or in-person for registered or new patients.
- **Walk-in & Emergency Registration:** Real-time queue insertion without prior scheduled slot; emergency priority flag elevates queue ordering.
- **Queue State Transition:** `booked` -> `arrived` (ticket generation) -> `in_progress` -> `done` (or `cancelled` / `no_show`).
- **Public Screen Integration:** Anonymized queue display for waiting room TVs (ticket identifiers like `A-001`, `B-014`, current consultation in room, upcoming queue list, and doctor delay status).

### 2.5 Clinical Consultations & Medical Records
- **Consultation Execution:** State progression to `in_progress` and recording of vital signs (BP systolic/diastolic, pulse, temperature, SpO2, weight, height).
- **Diagnosis & Prescriptions:** ICD/clinical diagnosis recording, internal medical notes (hidden from patient portal), structured dosage rules, and prescription generation.
- **Ancillary Orders:** Generation of laboratory test orders and billing invoice items for diagnostic tests, imaging (X-rays), and clinical procedures.
- **Automated Next-Patient Calling:** Completing a consultation triggers automatic queue advancement.

### 2.6 Laboratory Operations & Diagnostic Reports
- **Order Pipeline:** Structured workflow (`requested` -> `entered` -> `confirmed`).
- **Result Templates & Multi-Row Readings:** Discrete physiological test components with unit specifications and biological reference ranges (`ref_low`, `ref_high`).
- **Attachment Storage:** Secure upload of laboratory files (PDF, PNG, JPEG) up to 2MB to private Supabase Storage buckets.
- **Revision History:** Full version tracking on result corrections post-confirmation, noting timestamp, author, and prior readings.
- **Abnormal Value Alerts:** Automated notification delivery to the ordering physician when test readings violate reference boundaries.

### 2.7 Pharmacy & Stock Inventory
- **Real-time Stock Management:** Tracking medicine quantities, units (tablet, capsule, bottle, tube, injection, sachet), unit prices, low-stock thresholds, and batch expiry dates.
- **Barcode & GS1 Scanner Compatibility:** Global uniqueness enforcement on product barcodes.
- **Prescription Dispensing:** Expiration validation (within configurable clinic prescription validity window), atomic stock decrements, and automatic patient dosage instruction attachment.
- **Over-the-Counter (OTC) Sales:** Cash/counter direct sales with line-item valuation and idempotency protections.
- **Stock Movement Ledger:** Complete immutable audit log of all inventory mutations (`create`, `receive`, `dispense`, `edit`, `sale`).

### 2.8 Invoicing, Cash Registers & Accounting
- **Dual-Currency Invoicing:** Full support for Iraqi Dinar (IQD) and US Dollar (USD), with strict decimal arithmetic and separation.
- **Invoice Line Segregation:** Consultation fees, lab tests, X-rays, and medical procedures with immutable historical price capture.
- **Payment Lifecycle:** Cash and online settlement, deposit handling, partial settlements, refunds on cancellation/absence, and accountant reversal entries with mandatory reason justifications.
- **Shift & Cash Drawer Closing:** Tracking expected cash takings per receptionist shift against physical counts, computing discrepancy margins, and recording official closing summaries.
- **Expenses & Ledger:** Categorized operating expenditures (`rent`, `salaries`, `power`, `supplies`, `medicines`, `maintenance`, `other`) with voiding audit trails.
- **Doctor Dues Calculations:** Net earned fee distribution based on collected revenue, factoring in doctor contract percentages (`clinic_percent`, `service_percent`).

### 2.9 Management Reporting & Analytics
- **Executive Overview:** Real-time metrics on daily appointments, active queue loads, completed consultations, active staff, and physician counts.
- **Financial & Operational Analytics:** Multi-day trend charts, patient volume distribution by hour, method-of-payment breakdowns, frequent diagnoses, and patient review ratings.
- **Audit Trails:** Centralized security log recording actor, IP/client info, action category, target entity, and timestamp.

---

## 3. User Roles & Permission Matrix

| Operation / Area | Patient | Reception | Doctor | Pharmacy | Lab | Accountant | Manager |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **View Public Doctors & Queue Screen** | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **Manage Self/Family Profile** | Yes | No | No | No | No | No | No |
| **Book / Cancel / Reschedule Own Appts** | Yes | No | No | No | No | No | No |
| **Book Staff Appts / Walk-in / Check-in** | No | Yes | No | No | No | No | Yes |
| **Access Doctor Queue & Start/Finish Visit** | No | No | Own | No | No | No | No |
| **Record & Update Medical Alerts** | Read (Self) | Read | Yes (Assigned) | Read (Rx Alerts) | No | No | Read |
| **Record Vital Signs** | Read (Self) | Yes | Yes | No | No | No | Read |
| **View Full Medical History & Internal Notes** | Read (No Notes) | No | Yes (Assigned) | No | No | No | Read (No Notes) |
| **Enter & Confirm Lab Orders** | No | No | No | No | Yes | No | No |
| **View Lab Results** | Confirmed Only | No | Yes | No | Yes | No | Confirmed |
| **Dispense Rx & Manage Inventory** | No | No | Read Catalog | Yes | No | No | Read |
| **Accept Cash Payments / Shift Closing** | No | Yes | No | No | No | No | Read |
| **Reverse Payments / Manage Expenses / Ledger** | No | No | No | No | No | Yes | Yes |
| **Doctor Dues & Financial Summary Reports** | No | No | No | No | No | Yes | Yes |
| **Clinic Settings & Schedule Management** | No | No | No | No | No | No | Yes |
| **Staff Account Creation** | No | Staff only | No | No | No | No | All Roles |
| **Audit Log Inspection** | No | No | No | No | No | No | Yes |

---

## 4. Key Business Rules & State Transitions

1. **Appointment State Machine:**
   - `booked`: Validated slot, fee assigned, possible online deposit/full payment.
   - `arrived`: Triggered upon check-in (manual or offline sync) or walk-in registration. Issues ticket number formatted as `{DoctorLetter}-{000}`.
   - `in_progress`: Doctor starts consultation.
   - `done`: Doctor completes diagnosis, prescriptions, test orders, and procedure orders.
   - `cancelled`: Patient cancellation (permitted only if remaining time > `settings.cancel_hours`) or doctor absence (all active bookings cancelled and online payments refunded).
   - `no_show`: Marked by reception if slot has elapsed and patient failed to arrive. Counts against patient's deposit threshold (`no_shows >= settings.no_show_limit`).

2. **Deposit Requirement Rule:**
   - If a patient has accumulated `no_shows >= clinic_settings.no_show_limit`, they are prohibited from selecting the `"clinic"` pay option during self-booking. They must pay at least `clinic_settings.deposit_amount` via `"deposit"` or `"full"` online checkout.

3. **Concurrency & Double-Booking Prevention:**
   - Overlapping bookings for the same doctor on the same date/time interval are strictly prevented by a PostgreSQL exclusion constraint or transaction-level atomic serial lock.
   - Idempotency keys (`idempotency_key`) on appointment booking, payments, OTC sales, and stock operations guarantee that duplicate network transmissions result in idempotent returns without re-execution.

4. **Prescription Expiration & Dispensing:**
   - Prescriptions remain active for `clinic_settings.prescription_days` (default 7 days). Expired prescriptions cannot be dispensed.
   - Stock quantities must be verified for sufficient quantity and non-expired status (`expires_on >= today`) before debiting inventory. Dispensing operations are executed inside atomic database transactions.

5. **Financial Immutability & Reversals:**
   - No financial transaction is ever updated in place or deleted.
   - Online payments refunded due to cancellation create linked `"refund"` payment records.
   - Accountant adjustments create `"reversal"` records with explicit foreign-key references to the original transaction ID and logged textual justifications.

---

## 5. Existing Frontend API Contract Inventory

The frontend communicates with the backend via `Front/lib/api/http.ts` and `Front/lib/api/axios.ts`. Below is the complete enumeration of required HTTP operations:

### A. Authentication & Public
- `POST /auth/login` -> Request: `LoginRequest`, Response: `LoginResponse`
- `POST /auth/register` -> Request: `RegisterRequest`, Response: `LoginResponse`
- `POST /auth/logout` -> Request: `{ refresh_token?: string }`, Response: `null`
- `POST /auth/refresh` -> Request: `{ refresh_token: string }`, Response: `LoginResponse`
- `GET /public/doctors` -> Response: `Doctor[]`
- `GET /public/queue-screen` -> Response: `ScreenDoctor[]`

### B. Patient & Account
- `GET /me/family` -> Response: `FamilyMember[]`
- `POST /me/family` -> Request: `FamilyInput`, Response: `null`
- `PUT /me/family/{id}` -> Request: `FamilyInput`, Response: `null`
- `DELETE /me/family/{id}` -> Response: `null`
- `GET /me/appointments` -> Response: `MyAppointment[]`
- `GET /me/follow-ups` -> Response: `FollowUp[]`
- `GET /me/visits` -> Response: `MyVisit[]`
- `POST /me/visits/{visit_id}/rating` -> Request: `RateVisitRequest`, Response: `VisitRating`
- `GET /me/results` -> Response: `TestResult[]`
- `GET /me/notifications` -> Response: `AppNotification[]`
- `POST /me/notifications/read` -> Request: `{}`, Response: `null`
- `DELETE /me` -> Request: `{ password: string }`, Response: `null`

### C. Doctors & Appointments
- `GET /doctors/{doctor_id}/days` -> Response: `DoctorDay[]`
- `GET /doctors/{doctor_id}/slots?date={YYYY-MM-DD}&kind={new|followup}` -> Response: `Slot[]`
- `POST /appointments` -> Request: `BookRequest`, Response: `null`
- `POST /appointments/{id}/cancel` -> Request: `{}`, Response: `null`
- `POST /appointments/{id}/reschedule` -> Request: `RescheduleRequest`, Response: `null`
- `GET /patients/{patient_id}/booking-rules` -> Response: `BookingRules`
- `GET /appointments/booked-today` -> Response: `StaffAppointment[]`
- `POST /appointments/by-staff` -> Request: `StaffBookRequest`, Response: `StaffBookResult`
- `POST /appointments/{id}/check-in` -> Request: `{ emergency: boolean }`, Response: `null`
- `POST /walk-ins` -> Request: `WalkInRequest`, Response: `WalkInResult`
- `POST /appointments/{id}/no-show` -> Request: `{}`, Response: `null`
- `GET /doctors/{doctor_id}/queue` -> Response: `StaffAppointment[]`
- `POST /doctors/{doctor_id}/late` -> Request: `{ minutes: number }`, Response: `{ notified: number }`

### D. Doctor Clinical Operations
- `POST /appointments/{id}/start` -> Request: `{}`, Response: `null`
- `GET /patients/{patient_id}/alerts` -> Response: `MedicalAlerts`
- `PUT /patients/{patient_id}/alerts` -> Request: `MedicalAlerts`, Response: `MedicalAlerts`
- `PUT /appointments/{appointment_id}/vitals` -> Request: `Vitals`, Response: `VitalsRecord`
- `GET /patients/{patient_id}/vitals` -> Response: `VitalsRecord[]`
- `GET /patients/{patient_id}/visits` -> Response: `DoctorVisit[]`
- `POST /appointments/{id}/finish` -> Request: `FinishVisitRequest`, Response: `FinishVisitResult`

### E. Laboratory
- `GET /lab/orders` -> Response: `LabOrder[]`
- `PUT /lab/orders/{order_id}/result` -> Multipart or JSON: `ResultInput`, Response: `null`
- `POST /lab/orders/{order_id}/confirm` -> Request: `{}`, Response: `null`

### F. Pharmacy
- `GET /prescriptions` -> Response: `Prescription[]`
- `POST /prescriptions/{id}/dispense` -> Request: `DispenseRequest`, Response: `PharmacySale | null`
- `GET /pharmacy/catalog` -> Response: `CatalogMedicine[]`
- `GET /pharmacy/stock` -> Response: `StockItem[]`
- `POST /pharmacy/stock` -> Request: `StockInput`, Response: `null`
- `PUT /pharmacy/stock/{id}` -> Request: `StockInput`, Response: `null`
- `POST /pharmacy/stock/{id}/receive` -> Request: `ReceiveStockRequest`, Response: `null`
- `GET /pharmacy/stock/log?limit={n}` -> Response: `StockMove[]`
- `POST /pharmacy/sales` -> Request: `CounterSaleRequest`, Response: `PharmacySale`
- `GET /pharmacy/sales?date={YYYY-MM-DD}` -> Response: `PharmacySale[]`

### G. Invoicing, Payments & Cash Shift
- `POST /appointments/{appointment_id}/pay-cash` -> Request: `PayRequest`, Response: `null`
- `POST /appointments/{appointment_id}/pay-online` -> Request: `PayRequest`, Response: `null`
- `GET /invoices/today` -> Response: `Invoice[]`
- `GET /cash/shift` -> Response: `ShiftSummary`
- `POST /cash/closings` -> Request: `CloseShiftRequest`, Response: `CashClosing`
- `GET /cash/closings` -> Response: `CashClosing[]`
- `POST /payments/{payment_id}/reverse` -> Request: `{ reason: string }`, Response: `null`

### H. Manager & Administration
- `GET /users` -> Response: `StaffUser[]`
- `POST /users` -> Request: `CreateStaffRequest`, Response: `null`
- `GET /settings` -> Response: `ClinicSettings`
- `PUT /settings` -> Request: `ClinicSettings`, Response: `ClinicSettings`
- `GET /audit` -> Response: `AuditEntry[]`
- `GET /manager/overview` -> Response: `ManagerOverview`
- `GET /doctors/schedules` -> Response: `DoctorSchedule[]`
- `PUT /doctors/{doctor_id}/schedule` -> Request: `UpdateScheduleRequest`, Response: `null`
- `POST /doctors/{doctor_id}/absences` -> Request: `{ date: string }`, Response: `{ cancelled: number }`
- `GET /services` -> Response: `Service[]`
- `POST /services` -> Request: `ServiceInput`, Response: `null`
- `PUT /services/{service_id}` -> Request: `ServiceInput`, Response: `null`

### I. Accounting & Reports
- `GET /expenses?month={YYYY-MM}` -> Response: `Expense[]`
- `POST /expenses` -> Request: `ExpenseInput`, Response: `Expense`
- `POST /expenses/{id}/void` -> Request: `{ reason: string }`, Response: `Expense`
- `GET /ledger` -> Response: `LedgerEntry[]`
- `GET /reports/doctor-dues?month={YYYY-MM}` -> Response: `DoctorDues[]`
- `GET /reports/summary?month={YYYY-MM}` -> Response: `Report`
- `GET /manager/analytics?days={n}` -> Response: `Analytics`
- `GET /patients?q={query}` -> Response: `PatientSummary[]`
- `GET /patients/{patient_id}/file` -> Response: `PatientFile`

### J. Diagnostic & Infrastructure
- `GET /health` -> Response: `{ status: "ok", timestamp: string }`

---

## 6. Response Envelope & Error Specification

All responses adhere strictly to the expected Axios interceptor envelope:

**Success Response Envelope:**
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully"
}
```

**Failure Response Envelope:**
```json
{
  "success": false,
  "message": "Human readable error description",
  "code": "ERROR_CODE",
  "errors": { "field": ["details"] }
}
```

**Standard Error Codes:**
- `401`: `invalid_credentials`, `unauthorized`
- `403`: `forbidden`
- `404`: `not_found`
- `409`: `phone_taken`, `slot_taken`, `day_off`, `too_late`, `deposit_required`, `out_of_stock`, `stock_expired`, `barcode_taken`, `already_dispensed`, `already_rated`, `already_reversed`, `already_voided`, `member_has_bookings`
- `422`: `validation_error`, `bad_amount`, `bad_rating`, `future_date`
- `500`: `internal_server_error`
