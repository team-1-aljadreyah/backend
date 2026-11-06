# SECURITY & ROW LEVEL SECURITY (RLS) ARCHITECTURE
## Al-Jadreyah Clinic Management System

---

## 1. Security Architecture & Threat Model

Healthcare information systems require the highest standards of data confidentiality, integrity, and non-repudiation. The backend is designed with a defense-in-depth model:

1. **Transport Security:** All client-server and server-database communication must use TLS 1.3 / HTTPS.
2. **Identity Verification (Supabase Auth & JWT):** Stateless JWTs signed using HMAC-SHA256 / Ed25519, verifying issuer, audience, subject, and expiration.
3. **Role-Based Access Control (RBAC):** Verified role extracted from the database profile, never from client-provided payloads.
4. **Row Level Security (RLS):** Activated on all exposed tables in PostgreSQL, enforcing authorization at the storage engine level.
5. **Private Storage Protection:** Clinical files and diagnostic attachments are stored in a private Supabase Storage bucket (`lab-results`), accessible only via signed URLs or authenticated proxy endpoints.
6. **Immutable Audit Trails:** Sensitive clinical modifications, credential access, administrative changes, and financial reversals generate persistent records in `audit_logs`.

---

## 2. Row Level Security (RLS) Implementation

### 2.1 Context Resolution in PostgreSQL
PostgreSQL RLS policies evaluate the acting user through security definer helper functions:
- `get_current_profile_id()`: Returns the acting profile's numeric `id` corresponding to `auth.uid()`.
- `get_current_user_role()`: Returns the verified `user_role` enum for `auth.uid()`.
- `is_staff()`: Returns true if the acting user is one of `reception`, `doctor`, `pharmacy`, `lab`, `accountant`, or `manager`.

### 2.2 Security Policies by Domain

#### Patient Records & Medical Alerts (`patients`, `appointment_vitals`, `visits`)
- **Patients:** Can view exclusively their own profile and associated family members (`account_id = get_current_profile_id()`).
- **Doctors:** Can access files and medical alerts only for patients who have an active appointment or documented visit with that physician.
- **Reception & Management:** Can view demographic information and vital sign logs; reception is strictly prohibited from altering clinical diagnoses or internal medical notes.

#### Appointments & Queues (`appointments`)
- **Patients:** Permitted to query and book appointments only for their own file or registered family members.
- **Reception:** Authorized to manage bookings, check-ins, walk-ins, and queue re-ordering.
- **Doctors:** Restricted to inspecting and advancing their own clinical queue (`doctor_id = user.doctor_id`).

#### Diagnostic Lab Results (`lab_orders`)
- **Unconfirmed Results Quarantine:** Patients can never query or view lab results with status `requested` or `entered`. Only results marked `confirmed` are visible to patients.
- **Lab Technicians:** Permitted to input readings and update results. Any modification performed on a confirmed result automatically logs an entry in `history` preserving the prior result and author identity.

#### Invoicing & Financial Transactions (`payments`, `invoice_items`, `cash_closings`, `expenses`)
- **Patients:** Can only inspect invoices and payments directly attached to their own appointments.
- **Reception:** Permitted to accept payments for today's visits and submit shift closings for their own register.
- **Accountant & Manager:** Authorized to inspect all payments, execute ledger reversals with mandatory audit reasons, record clinic expenditures, and void erroneous expenses.
- **Immutability Guarantee:** Hard deletions (`DELETE`) are disabled on `payments` and `expenses`. Reversals create opposite entries linked by `ref_id`.

#### Pharmacy Inventory & Dispensing (`stock_items`, `stock_moves`, `pharmacy_sales`)
- **Stock Management:** Only `pharmacy` and `manager` roles can modify stock items, receive deliveries, and execute sales.
- **Audit Logging:** Every stock modification records a corresponding record in `stock_moves` with actor, change quantity, and resulting on-hand count.

---

## 3. Defense against Common Web Vulnerabilities

### 3.1 Broken Object Level Authorization (BOLA / IDOR)
Every endpoint receiving an identifier (`patient_id`, `appointment_id`, `visit_id`, `order_id`) executes server-side ownership checks before processing:
- Patient endpoints verify `ownedPatientIds(user).includes(patient_id)`.
- Doctor endpoints verify that the physician has an active clinical relationship with the patient.

### 3.2 Concurrent Double Booking & Race Conditions
To prevent concurrent requests from reserving the exact same time slot for a doctor:
- Database-level partial unique index:
  ```sql
  CREATE UNIQUE INDEX idx_unique_doctor_active_slot
      ON appointments (doctor_id, date, time)
      WHERE status IN ('booked', 'arrived', 'in_progress', 'done') AND time <> '';
  ```
- Any simultaneous attempt by two patients to book the same slot results in an immediate database constraint violation caught gracefully as a `409 slot_taken` error.

### 3.3 Idempotency Protection
Critical mutating endpoints accept an `idempotency_key` header/field:
- `POST /appointments`
- `POST /appointments/by-staff`
- `POST /appointments/{id}/pay-cash`
- `POST /appointments/{id}/pay-online`
- `POST /pharmacy/sales`
Duplicate transmissions return the existing resource without performing duplicate debits or reservations.

### 3.4 Rate Limiting & DoS Protection
Authentication endpoints (`/auth/login`, `/auth/register`) and payment endpoints implement IP and phone-based rate limits to mitigate brute-force and credential stuffing attacks.
