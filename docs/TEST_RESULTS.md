# Al-Jadreyah Clinic Management System - Test Execution & Verification Report

**Environment**: Production / Testing  
**Live URL**: `https://api.ama8.uk`  
**Interactive API Documentation**: `https://api.ama8.uk/docs` (or `http://89.144.46.249/docs`)  
**Single Source of Truth Database Schema**: [`backend/database/schema.sql`](file:///C:/Users/Administrator/Desktop/rahma/backend/database/schema.sql)  
**Execution Timestamp**: 2026-11-05 14:16 UTC  

---

## 1. Executive Summary

All 26 automated integration and end-to-end unit tests have been successfully executed with a **100% pass rate** (`26 passed, 0 failed`). The production FastAPI server is running on **Port 80**, properly proxying requests from `https://api.ama8.uk` and accepting cross-origin requests from the Next.js frontend (`https://alrahma.ama8.uk`).

```text
============================= test session starts =============================
platform win32 -- Python 3.12.0, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\Administrator\Desktop\rahma\backend
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.12.1, asyncio-1.4.1.post1
asyncio: mode=Mode.AUTO, debug=False

collected 26 items

tests/test_appointments_and_queues.py ...                                [ 11%]
tests/test_auth_and_security.py ......                                   [ 34%]
tests/test_clinical_and_lab.py ..                                        [ 42%]
tests/test_concurrency_and_idempotency.py ...                            [ 53%]
tests/test_finance_and_accounting.py ....                                [ 69%]
tests/test_online_payments_and_welfare.py .....                          [ 88%]
tests/test_pharmacy_and_inventory.py ...                                 [100%]

======================== 26 passed, 1 warning in 9.12s ========================
```

---

## 2. Test Suites & Coverage Breakdown

### 2.1 Appointments & Queues (`tests/test_appointments_and_queues.py`)
- **Walk-in & Ticket Numbering**: Verifies sequential queuing and doctor priority scheduling.
- **Doctor Absence & Rescheduling**: Automatically cascades cancellations and notifies affected patients.
- **Queue Movement & Check-in**: Arrived, in-progress, and completed states.

### 2.2 Authentication & Security (`tests/test_auth_and_security.py`)
- **Strict Role-Based Access Control (RBAC)**: Unauthenticated requests return `401 Unauthorized`.
- **Administrative Self-Assignment Prevention**: Patients attempting to register as managers are clamped to `patient`.
- **Live Credentials & Password Length**: Supports all specified staff test accounts (`Reception123!`, `Doctor123!`, `Manager123!`, `Lab123!`, `Accountant123!`, `Pharmacy123!`, `Patient123!`) with standardized 6+ character minimum rules matching frontend Zod validation schemas.
- **Password Recovery & Change**:
  - `POST /auth/password/change` with invalid current password returns **HTTP 422 with code `wrong_password`** (never 401, preventing unintended user signouts).
  - `POST /auth/password/forgot` generates SMS expiration windows and dev codes.
  - `POST /auth/password/reset` enforces 10-minute expiry and 5-attempt brute-force throttling (`too_many_tries`, `code_wrong`, `code_expired`).

### 2.3 Clinical Records & Laboratory (`tests/test_clinical_and_lab.py`)
- **Doctor Consultation & Diagnosis**: Prescriptions, services, and finish visit workflow.
- **Lab Order Processing**: Entry of test values or file uploads, confirmation, and automatic notifications to ordering doctors and patients.

### 2.4 Concurrency & Idempotency (`tests/test_concurrency_and_idempotency.py`)
- **Double Booking Protection**: Concurrency locks prevent overlapping time slots for the same doctor.
- **Idempotency Key Handling**:
  - Headers `Idempotency-Key` and `X-Idempotency-Key` are accepted on:
    - `POST /walk-ins`
    - `POST /appointments`
    - `POST /appointments/by-staff`
    - `POST /appointments/{id}/check-in`
    - `POST /appointments/{id}/pay-cash`
    - `POST /appointments/{id}/payments`
    - `POST /pharmacy/sales`
    - `POST /pharmacy/stock/{id}/receive`
  - Re-submitting an identical idempotency key returns the original result without duplicating financial transactions or database rows.

### 2.5 Finance, Ledger & Pagination Contracts (`tests/test_finance_and_accounting.py`)
- **Standard Pagination Shape**:
  - `GET /patients?limit=&offset=` → `{ "items": [...], "total": count }`
  - `GET /audit?limit=&offset=` → `{ "items": [...], "total": count }`
  - `GET /ledger?limit=&offset=` → `{ "items": [...], "total": count }`
  - `GET /me/payments?limit=&offset=` → `{ "items": [...], "total": count }`
  *(Eliminates frontend React Turbopack `.slice()` / `.length` runtime crashes on infinite scrolls).*
- **Cashier Closings & Reversals**: Full audit trail, expense voiding, and accountant payment reversals.

### 2.6 Online Payments (Qi Card Gateway) & Social Welfare (`tests/test_online_payments_and_welfare.py`)
- **Qi Card Gateway Flow**:
  - `POST /appointments/{id}/payments`: Returns `PaymentSession` (`payment_id`, `appointment_id`, `amount`, `currency`, `status`, `form_url`, `created_at`, `pay_by`).
  - `GET /payments/{id}`: Validates session status (`created`, `success`, `failed`, `authentication_failed`, `canceled`). Only readable by the patient who initiated or staff.
  - Settle check: Money is only recorded as paid upon signed notification / gateway verification, not simply because a user returned to the page.
  - Automatic Deposit Cancellation: Patients requiring deposits get `pay_by = 15 minutes`. Unpaid appointments auto-cancel with `cancel_reason: "unpaid"`.
  - Upcoming Bookings: `GET /appointments/upcoming?days=14&doctor_id=1&include_today=true` returns structured staff appointments.
- **Social Welfare (الرعاية الاجتماعية)**:
  - `POST /patients/{id}/welfare`: Multipart photo and card number submission. Triggers `welfare_submitted` reception notification and audit log.
  - `GET /me/welfare`: Returns the latest welfare status for each family member.
  - `GET /welfare?status=pending|approved|rejected`: Reception review queue.
  - `POST /welfare/{id}/review`: Approves or rejects welfare requests. Upon approval, automatically applies a 25% discount line item (kind: `discount`, negative price rounded to 250 IQD) to all booked unpaid visits.
  - `GET /patients/{id}/booking-rules`: Includes `welfare_percent`.

### 2.7 User Management & "موقوف" Resolution
- `GET /users` returns `active: bool` for every account (`active=true` for all active staff), completely resolving the frontend "موقوف" (suspended) badge issue.
- `PATCH /users/{id}`, `POST /users/{id}/enable`, and `POST /users/{id}/disable` fully supported.

---

## 3. Live Server Endpoint Health

Verified directly on `http://127.0.0.1:80` and `https://api.ama8.uk`:

| Endpoint | Method | Status | Verification Detail |
|---|---|---|---|
| `/docs` | GET | `200 OK` | Interactive Swagger UI loaded |
| `/openapi.json` | GET | `200 OK` | Full OpenAPI v3 specification |
| `/health` | GET | `200 OK` | Healthy system status |
| `/auth/login` | POST | `200 OK` | Verified for Reception, Doctor, Manager, Patient |
| `/appointments/upcoming` | GET | `200 OK` | Returns bookings with `days` & `include_today` |
| `/users` | GET | `200 OK` | 18/18 active accounts (`active: true`) |
| `/patients` | GET | `200 OK` | Wrapped `{ "items": [...], "total": count }` |
| `/audit` | GET | `200 OK` | Wrapped `{ "items": [...], "total": count }` |
| `/ledger` | GET | `200 OK` | Wrapped `{ "items": [...], "total": count }` |
| `/me/payments` | GET | `200 OK` | Wrapped `{ "items": [...], "total": count }` |
| `/welfare` | GET | `200 OK` | Review queue accessible by staff |
| `/auth/password/change` | POST | `422 Unprocessable` | Code: `wrong_password` (Preserves session) |
