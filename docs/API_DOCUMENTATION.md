# Al-Jadreyah Clinic Management System — API Documentation

This document describes the complete HTTP REST API for the Al-Jadreyah Clinic Management System backend.

The backend conforms strictly to the frontend API contract consumed by the Next.js client (`Front/lib/api/http.ts` and `Front/lib/api/types.ts`).

---

## 1. Global API Standards

### 1.1 Base URL
- Local Development: `http://localhost:8000`
- Production: `https://api.aljadreyah-clinic.iq` (or designated Supabase/Cloud host)

### 1.2 Response Envelope
All API endpoints return standard JSON envelopes structured as follows:

**Successful Response (HTTP 200 / 201):**
```json
{
  "success": true,
  "data": <Payload | null>
}
```

**Error Response (HTTP 4xx / 5xx):**
```json
{
  "success": false,
  "message": "Human-readable explanation of the error",
  "code": "machine_readable_error_code",
  "errors": {
    "field_name": "Field-specific validation issue"
  }
}
```

### 1.3 Authentication
All protected routes require an RFC 7519 Bearer token in the `Authorization` header:
```http
Authorization: Bearer <jwt_access_token>
```

Tokens are standard HS256 JWTs carrying:
- `sub`: User profile ID (numeric string)
- `role`: One of `patient`, `reception`, `doctor`, `pharmacy`, `lab`, `accountant`, `manager`
- `exp`: Expiration Unix epoch timestamp

---

## 2. Authentication & Session Endpoints

### `POST /auth/login`
Authenticates a user by Iraqi phone number (`07XXXXXXXXX` or `+9647XXXXXXXXX`) and password.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "phone": "07701234567",
    "password": "Password123"
  }
  ```
- **Response `data`:**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "name": "سارة الاستقبال",
      "phone": "07701234567",
      "role": "reception",
      "doctor_id": null
    }
  }
  ```

### `POST /auth/register`
Self-service patient registration. Strictly assigns `role: "patient"` and creates the primary patient medical file.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "name": "حيدر علي",
    "phone": "07705556677",
    "password": "SecurePassword123"
  }
  ```
- **Response `data`:** Same structure as `/auth/login`.

### `POST /auth/refresh`
Refreshes an expired access token using a valid refresh token.
- **Access:** Public
- **Request Body:**
  ```json
  {
    "refresh_token": "eyJhbGciOi..."
  }
  ```
- **Response `data`:**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi...",
    "token_type": "bearer"
  }
  ```

### `POST /auth/logout`
Revokes the refresh token and invalidates the session.
- **Access:** Public / Authenticated
- **Request Body:**
  ```json
  {
    "refresh_token": "eyJhbGciOi..."
  }
  ```
- **Response `data`:** `null`

---

## 3. Public Endpoints

### `GET /public/doctors`
Returns public profiles of all active doctors for directory listing and patient booking.
- **Access:** Public
- **Response `data`:** Array of `Doctor` objects:
  ```json
  [
    {
      "id": 1,
      "name": "Dr. Ahmed Al-Saadi",
      "name_ar": "د. أحمد السعدي",
      "specialty": "الباطنية والقلبية",
      "fee": 25000,
      "follow_up_fee": 10000,
      "room": "عيادة 101",
      "active": true
    }
  ]
  ```

### `GET /public/queue-screen`
Returns real-time queue display data for the clinic waiting room TV screens. Privacy-preserving (shows ticket numbers, zero patient names).
- **Access:** Public
- **Response `data`:** Array of `ScreenDoctor` objects:
  ```json
  [
    {
      "doctor_id": 1,
      "doctor_name": "د. أحمد السعدي",
      "room": "عيادة 101",
      "current_ticket": 12,
      "waiting_count": 4,
      "next_tickets": [13, 14, 15]
    }
  ]
  ```

---

## 4. Patient Portal (`/me`)

### `GET /me`
Retrieves the logged-in user profile.
- **Access:** Any authenticated user
- **Response `data`:** `User` object.

### `DELETE /me`
Deletes the user's online account while preserving their medical file with the clinic. Requires password confirmation.
- **Access:** `patient`
- **Request Body:** `{"password": "Password123"}`
- **Response `data`:** `null`

### `GET /me/family`
Lists all family members linked to the patient's account.
- **Access:** `patient`
- **Response `data`:** Array of `FamilyMember` objects:
  ```json
  [
    {
      "id": 2,
      "name": "زينب علي",
      "relation": "daughter",
      "birth_date": "2018-05-14",
      "phone": "07705556677"
    }
  ]
  ```

### `POST /me/family`
Registers a family member under the patient's account.
- **Access:** `patient`
- **Request Body:**
  ```json
  {
    "name": "زينب علي",
    "relation": "daughter",
    "birth_date": "2018-05-14",
    "phone": "07705556677"
  }
  ```
- **Response `data`:** `null`

### `PUT /me/family/{id}`
Updates details for a linked family member.
- **Access:** `patient` (must own the family member)
- **Response `data`:** `null`

### `DELETE /me/family/{id}`
Unlinks a family member from the account.
- **Access:** `patient` (must own the family member)
- **Response `data`:** `null`

### `GET /me/appointments`
Returns all past and upcoming appointments for the account holder and their family members.
- **Access:** `patient`
- **Response `data`:** Array of `MyAppointment` objects.

### `GET /me/follow-ups`
Lists physician-requested follow-ups that haven't been booked yet.
- **Access:** `patient`
- **Response `data`:** Array of `FollowUp` objects with target dates and physician names.

### `GET /me/visits`
Returns the consultation history and visit summaries for the patient and their family.
- **Access:** `patient`
- **Response `data`:** Array of `MyVisit` objects.

### `POST /me/visits/{id}/rating`
Submits a rating and feedback for a completed visit (1-5 stars). Can only be performed once per visit.
- **Access:** `patient`
- **Request Body:** `{"rating": 5, "comment": "عناية ممتازة"}`
- **Response `data`:** `VisitRating` object.

### `GET /me/results`
Returns completed laboratory test results for the patient and family.
- **Access:** `patient`
- **Response `data`:** Array of `TestResult` objects.

### `GET /me/notifications`
Returns active notifications (appointment confirmations, lab ready alerts, delays).
- **Access:** Any authenticated user
- **Response `data`:** Array of `AppNotification` objects.

### `POST /me/notifications/read`
Marks all pending notifications as read.
- **Access:** Any authenticated user
- **Response `data`:** `null`

---

## 5. Doctors & Scheduling

### `GET /doctors/{id}/days`
Returns the 14-day schedule window for a doctor, indicating which days are working days.
- **Access:** Authenticated
- **Response `data`:** Array of `DoctorDay`:
  ```json
  [
    {
      "date": "2026-11-05",
      "work": true,
      "shift": "morning",
      "branch": "main"
    }
  ]
  ```

### `GET /doctors/{id}/slots`
Returns all appointment slots for a specific date and consultation kind (`new` or `followup`), indicating real-time availability.
- **Access:** Authenticated
- **Query Parameters:** `date=YYYY-MM-DD`, `kind=new|followup`
- **Response `data`:** Array of `Slot`:
  ```json
  [
    {"time": "09:00", "available": true},
    {"time": "09:20", "available": false}
  ]
  ```

### `GET /doctors/{id}/queue`
Returns the active waiting and called queue for a doctor today.
- **Access:** `doctor`, `reception`, `manager`
- **Response `data`:** Array of `StaffAppointment` ordered by urgency and arrival order.

### `GET /doctors/schedules`
Lists working hours and shift configs for all doctors.
- **Access:** `reception`, `manager`
- **Response `data`:** Array of `DoctorSchedule`.

### `PUT /doctors/{id}/schedule`
Updates a doctor's weekly working days, hours, and appointment durations.
- **Access:** `manager`
- **Request Body:** `UpdateScheduleRequest`
- **Response `data`:** `null`

### `POST /doctors/{id}/absences`
Records an emergency absence for a doctor on a specific date. Automatically cancels all booked appointments, refunds payments, and notifies patients.
- **Access:** `manager`, `reception`
- **Request Body:** `{"date": "2026-11-06"}`
- **Response `data`:** `{"cancelled": 8}`

### `POST /doctors/{id}/late`
Broadcasts an SMS/in-app alert to all patients booked for the doctor today indicating an unexpected delay.
- **Access:** `manager`, `reception`
- **Request Body:** `{"minutes": 30}`
- **Response `data`:** `{"notified": 12}`

---

## 6. Appointments & Queues

### `POST /appointments`
Patient self-service booking. Atomic and protected against concurrency double-booking. Supports idempotency keys.
- **Access:** `patient`
- **Request Body:**
  ```json
  {
    "patient_id": 1,
    "doctor_id": 1,
    "date": "2026-11-05",
    "time": "09:00",
    "kind": "new",
    "pay": "clinic",
    "idempotency_key": "uuid-here"
  }
  ```
- **Response `data`:** `null`

### `POST /appointments/{id}/cancel`
Cancels a booked appointment within the allowed cancellation window.
- **Access:** `patient` (owner), `reception`, `manager`
- **Response `data`:** `null`

### `POST /appointments/{id}/reschedule`
Moves an appointment to a new date and time slot atomically.
- **Access:** `patient` (owner), `reception`, `manager`
- **Request Body:** `{"date": "2026-11-07", "time": "10:00"}`
- **Response `data`:** `null`

### `POST /appointments/by-staff`
Receptionist booking on behalf of a patient (phone caller or counter visitor). Finds or creates the patient record.
- **Access:** `reception`, `manager`
- **Request Body:** `StaffBookRequest`
- **Response `data`:** `{"patient_id": 1}`

### `GET /appointments/booked-today`
Returns all appointments scheduled for today across all doctors.
- **Access:** `reception`, `manager`
- **Response `data`:** Array of `StaffAppointment`.

### `POST /appointments/{id}/check-in`
Checks in an arrived patient, transitions status to `arrived`, and issues a queue ticket.
- **Access:** `reception`, `manager`
- **Request Body:** `{"emergency": false}`
- **Response `data`:** `null`

### `POST /appointments/{id}/no-show`
Marks an absent patient as `no_show`. Increments no-show counter.
- **Access:** `reception`, `manager`
- **Response `data`:** `null`

### `POST /walk-ins`
Registers an unscheduled walk-in patient directly into today's queue. Performs fuzzy matching to prevent duplicate patient creation.
- **Access:** `reception`, `manager`
- **Request Body:**
  ```json
  {
    "name": "أحمد محمود",
    "phone": "07712345678",
    "doctor_id": 1,
    "emergency": true
  }
  ```
- **Response `data`:** `{"duplicate": false, "patient_id": 12}`

### `GET /patients/{id}/booking-rules`
Checks account reliability metrics (past no-shows, deposit required threshold, deposit amount).
- **Access:** Authenticated
- **Response `data`:** `BookingRules`

---

## 7. Clinical & Consultations

### `POST /appointments/{id}/start`
Doctor starts the consultation with the arrived patient. Sets status to `in_progress`.
- **Access:** `doctor`, `manager`
- **Response `data`:** `null`

### `PUT /appointments/{id}/vitals`
Records triage vital signs (blood pressure systolic/diastolic, temperature, pulse, SpO2, weight, height).
- **Access:** `reception`, `doctor`, `manager`
- **Request Body:** `Vitals`
- **Response `data`:** `Vitals`

### `POST /appointments/{id}/finish`
Completes the medical visit. Records diagnosis, prescriptions, test orders, procedures, and follow-up requests in a single transaction. Automatically calls the next waiting patient.
- **Access:** `doctor`, `manager`
- **Request Body:**
  ```json
  {
    "diagnosis": "ارتفاع ضغط الدم الشرياني",
    "internal_note": "Confidential doctor note",
    "medicines": [
      {"name": "Amlodipine 5mg", "dose": "1/1", "days": 30}
    ],
    "test_ids": [1],
    "procedure_ids": [],
    "follow_up_days": 14
  }
  ```
- **Response `data`:** `{"next_ticket": 14}` (or `null` if queue empty).

---

## 8. Laboratory Management

### `GET /lab/orders`
Lists all laboratory test orders awaiting processing or results.
- **Access:** `lab`, `manager`
- **Response `data`:** Array of `LabOrder`.

### `PUT /lab/orders/{id}/result`
Enters test results. Supports both structured numerical values with reference ranges (JSON) and report document/image uploads (multipart/form-data via Supabase Storage).
- **Access:** `lab`, `manager`
- **Request Body:** `ResultInput`
- **Response `data`:** `null`

### `POST /lab/orders/{id}/confirm`
Finalizes and locks the laboratory result. Transitions order status to `completed` and notifies the patient and ordering doctor.
- **Access:** `lab`, `manager`
- **Response `data`:** `null`

---

## 9. Pharmacy & Medicine Inventory

### `GET /prescriptions`
Lists all active prescriptions generated by doctors.
- **Access:** `pharmacy`, `manager`
- **Response `data`:** Array of `Prescription`.

### `POST /prescriptions/{id}/dispense`
Dispenses prescribed medications to the patient, automatically decrements stock levels, records stock movement audit records, and produces a pharmacy sale receipt.
- **Access:** `pharmacy`, `manager`
- **Request Body:** `DispenseRequest`
- **Response `data`:** `PharmacySale`

### `POST /pharmacy/sales`
Over-the-counter medication sale without a prescription. Validates stock availability, deducts inventory atomically, and produces a sale receipt.
- **Access:** `pharmacy`, `manager`
- **Request Body:**
  ```json
  {
    "customer": "زائر",
    "lines": [
      {"stock_id": 60, "quantity": 2}
    ],
    "idempotency_key": "uuid"
  }
  ```
- **Response `data`:** `PharmacySale`

### `GET /pharmacy/sales`
Returns all sales executed on a specific date (`YYYY-MM-DD`).
- **Access:** `pharmacy`, `accountant`, `manager`
- **Response `data`:** Array of `PharmacySale`.

### `GET /pharmacy/stock`
Lists all medicines in stock, showing current quantity, low stock warning status, and expiration dates.
- **Access:** `pharmacy`, `manager`
- **Response `data`:** Array of `StockItem`.

### `GET /pharmacy/catalog`
Provides a simplified search catalog of available medicines for doctors during prescription writing.
- **Access:** `doctor`, `pharmacy`, `manager`
- **Response `data`:** Array of `CatalogMedicine`.

### `POST /pharmacy/stock`
Adds a new medicine item to the inventory.
- **Access:** `pharmacy`, `manager`
- **Request Body:** `StockInput`
- **Response `data`:** `null`

### `PUT /pharmacy/stock/{id}`
Updates medicine attributes, pricing, or alert thresholds.
- **Access:** `pharmacy`, `manager`
- **Response `data`:** `null`

### `POST /pharmacy/stock/{id}/receive`
Records a newly received shipment/batch of medications. Increments stock quantity and updates expiry date.
- **Access:** `pharmacy`, `manager`
- **Request Body:** `{"quantity": 100, "expires_on": "2028-01-01"}`
- **Response `data`:** `null`

### `GET /pharmacy/stock/log`
Returns an immutable audit log of all stock movements (dispense, sale, intake, adjustment).
- **Access:** `pharmacy`, `manager`
- **Query Parameters:** `limit=50`
- **Response `data`:** Array of `StockMove`.

---

## 10. Financials, Invoicing & Cashier

### `GET /invoices/today`
Returns all patient consultation invoices for today, showing total billed, paid amount, and outstanding balance in IQD and USD.
- **Access:** `reception`, `accountant`, `manager`
- **Response `data`:** Array of `Invoice`.

### `POST /appointments/{id}/pay-cash`
Records a cash payment at the reception counter. Validates that payment does not exceed outstanding balance. Idempotent.
- **Access:** `reception`, `accountant`, `manager`
- **Request Body:**
  ```json
  {
    "amount": 25000,
    "currency": "IQD",
    "idempotency_key": "uuid"
  }
  ```
- **Response `data`:** `null`

### `POST /appointments/{id}/pay-online`
Initiates an electronic payment transaction via integrated gateway (ZainCash, AsiaHawala, QiCard).
- **Access:** `patient`, `reception`, `accountant`, `manager`
- **Request Body:** `PayRequest`
- **Response `data`:** `null`

### `GET /cash/shift`
Returns current receptionist shift cash reconciliation: expected cash collected since last closing vs counted cash.
- **Access:** `reception`, `accountant`, `manager`
- **Response `data`:** `ShiftSummary`.

### `POST /cash/closings`
Closes the receptionist shift, records counted cash vs expected cash, calculates discrepancies, and seals the register.
- **Access:** `reception`, `manager`
- **Request Body:**
  ```json
  {
    "counted": {"IQD": 350000, "USD": 0},
    "note": "وردية الصباح مكتملة"
  }
  ```
- **Response `data`:** `CashClosing`.

### `GET /cash/closings`
Lists historical cash closings. Receptionists view their own closings; accountant and manager view all staff closings.
- **Access:** `reception`, `accountant`, `manager`
- **Response `data`:** Array of `CashClosing`.

### `GET /expenses`
Lists clinic operational expenses for a specific month (`YYYY-MM`), including voided records for audit trail integrity.
- **Access:** `accountant`, `manager`
- **Query Parameters:** `month=YYYY-MM`
- **Response `data`:** Array of `Expense`.

### `POST /expenses`
Records a clinic expense (supplies, maintenance, utilities, salary advances).
- **Access:** `accountant`, `manager`
- **Request Body:** `ExpenseInput`
- **Response `data`:** `Expense`.

### `POST /expenses/{id}/void`
Non-destructively voids an incorrect expense with mandatory explanation reason.
- **Access:** `accountant`, `manager`
- **Request Body:** `{"reason": "خطأ في تسعير الفاتورة"}`
- **Response `data`:** `Expense`.

### `GET /ledger`
Returns the complete financial audit ledger of all money movements.
- **Access:** `accountant`, `manager`
- **Response `data`:** Array of `LedgerEntry`.

### `POST /payments/{id}/reverse`
Non-destructively reverses an erroneous payment by creating an opposing debit/credit record with justification.
- **Access:** `accountant`, `manager`
- **Request Body:** `{"reason": "دفع مكرر بالخطأ"}`
- **Response `data`:** `null`

---

## 11. Reports & Analytics

### `GET /reports/doctor-dues`
Calculates doctor compensation for a given month (`YYYY-MM`) based on consultation fees, procedures, clinic percentage cuts, and visits completed.
- **Access:** `accountant`, `manager`
- **Query Parameters:** `month=YYYY-MM`
- **Response `data`:** Array of `DoctorDues`.

### `GET /reports/summary`
Comprehensive monthly financial report: total patient visits, revenues, expenses, net profit, outstanding debts, and department breakdowns.
- **Access:** `manager`, `accountant`
- **Query Parameters:** `month=YYYY-MM`
- **Response `data`:** `Report`.

### `GET /manager/analytics`
Managerial dashboard charts and metrics for the past `days` (today included): daily revenues, patient visits, specialty popularity, new vs return patient ratios.
- **Access:** `manager`
- **Query Parameters:** `days=14`
- **Response `data`:** `Analytics`.

### `GET /manager/overview`
High-level today overview: today revenue, active waiting patients, doctors currently on duty, pending lab tests, low stock alerts.
- **Access:** `manager`
- **Response `data`:** `ManagerOverview`.

---

## 12. Administration, Users & Settings

### `GET /users`
Lists all staff members (doctors, receptionists, lab technicians, pharmacists, accountants, managers).
- **Access:** `manager`
- **Response `data`:** Array of `StaffUser`.

### `POST /users`
Provisions a new staff user account with assigned role and doctor association if applicable.
- **Access:** `manager`
- **Request Body:** `CreateStaffRequest`
- **Response `data`:** `null`

### `GET /settings`
Retrieves global clinic configuration parameters.
- **Access:** `manager`, `reception`
- **Response `data`:** `ClinicSettings`.

### `PUT /settings`
Updates global clinic configuration parameters (cancellation policy, no-show penalty threshold, deposit amount).
- **Access:** `manager`
- **Request Body:** `ClinicSettings`
- **Response `data`:** `ClinicSettings`.

### `GET /services`
Lists all clinical services, diagnostic lab tests, and procedures with standard pricing.
- **Access:** Authenticated
- **Response `data`:** Array of `Service`.

### `POST /services`
Creates a new clinical or laboratory service.
- **Access:** `manager`
- **Request Body:** `ServiceInput`
- **Response `data`:** `null`

### `PUT /services/{id}`
Updates service details, pricing, or department category.
- **Access:** `manager`
- **Response `data`:** `null`

### `GET /audit`
Returns system audit log entries capturing critical business operations, security actions, and data changes.
- **Access:** `manager`
- **Response `data`:** Array of `AuditEntry`.

---

## 13. System Health

### `GET /health`
Liveness and readiness probe for orchestration (Docker, Kubernetes, Cloud Run). Verifies database connectivity and latency.
- **Access:** Public
- **Response `data`:**
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "version": "1.0.0",
    "environment": "production"
  }
  ```
