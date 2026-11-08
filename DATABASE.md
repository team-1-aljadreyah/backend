# Database Architecture & Security Specification

This document details the relational data model, concurrency constraints, Row Level Security (RLS) policies, and role architecture of the Al-Jadreyah Clinic Management System.

---

## 1. Relational Schema & Tables

The system operates on PostgreSQL 16+ (Supabase) organized into cohesive business domains:

### Clinical & Appointments
- `branches`: Physical clinic facilities (`main`, `second`).
- `doctors`: Doctor profiles, specialty, fees, duration settings, working schedules (`days`), absences, and delay settings.
- `patients`: Master patient directory with normalized names, phone numbers, account linkage, and merge audit trail (`merged_into_patient_id`).
- `appointments`: Scheduled and walk-in visits. Protected by PostgreSQL GiST exclusion constraint (`tsrange(start_time, end_time)` per doctor) and optimistic/row locking.
- `appointment_vitals`: Pre-consultation vitals (BP, pulse, temp, weight, height, glucose) collected by nursing or triage staff.
- `visits`: Completed clinical encounters, diagnoses, internal doctor notes, and prescribed medication lines.
- `services`: Master catalog of medical procedures and lab tests with pricing.
- `lab_orders`: Diagnostic orders with sample tracking, results entry, and technician confirmation timestamps.

### Pharmacy & Inventory
- `stock_items`: Medication inventory, unit cost, packaging units, and reorder alerts.
- `stock_moves`: Complete audit trail of inventory adjustments (purchases, adjustments, disposals).
- `pharmacy_sales`: Over-the-counter and prescription dispensing records.

### Finance & Billing
- `invoice_items`: Itemized charges attached to an appointment (consultation fee, procedures, discounts).
- `payments`: Immutable financial ledger entries (cash, online payments, reversals, and refunds).
- `payment_sessions`: Qi Card gateway payment sessions, transaction keys, statuses, and settlement outcomes.
- `cash_closings`: End-of-shift cash drawer reconciliations signed off by reception and accountants.
- `expenses`: Clinic operational expenditure categorized by department.

### Real-Time, Infrastructure & Governance (PostgreSQL-Only)
- `outbox_events`: Transactional outbox events for cross-worker event delivery via `pg_notify`.
- `realtime_connection_tickets`: Single-use SHA-256 hashed WebSocket authentication tickets.
- `rate_limit_entries`: Distributed sliding-window rate limit counters for authentication endpoints.
- `welfare_requests`: Social welfare discount applications (رعاية اجتماعية) with review statuses.
- `patient_merges`: Historical record of merged patient profiles and transferred medical records.
- `idempotency_records`: Cryptographic request-hash cache preventing duplicate transaction execution.
- `user_sessions`: Active and revoked JWT refresh tokens.
- `password_reset_otps`: Secure SMS verification codes for password recovery.
- `audit_logs`: Immutable clinical and administrative activity audit log.
- `notifications`: User-facing notification records.

---

## 2. Concurrency & Data Integrity Controls

1. **GiST Exclusion Constraint on Appointments:**
   ```sql
   ALTER TABLE appointments ADD CONSTRAINT no_overlapping_appointments
   EXCLUDE USING gist (
       doctor_id WITH =,
       tsrange(start_time, end_time) WITH &&
   ) WHERE (status IN ('booked', 'arrived', 'in_progress'));
   ```
   Guarantees at the database engine level that no doctor can be double-booked for overlapping time ranges, even under high concurrency.
2. **Deterministic Row Locking:** Critical booking and ticket allocation operations serialize through `SELECT ... FOR UPDATE` on the target doctor row, preventing race conditions.
3. **Transactional Outbox Trigger:**
   ```sql
   CREATE OR REPLACE FUNCTION notify_outbox_event()
   RETURNS TRIGGER AS $$
   BEGIN
       PERFORM pg_notify('realtime_events', NEW.id::text);
       RETURN NEW;
   END;
   $$ LANGUAGE plpgsql;

   CREATE TRIGGER trg_outbox_event_notify
   AFTER INSERT ON outbox_events
   FOR EACH ROW
   EXECUTE FUNCTION notify_outbox_event();
   ```

---

## 3. Database Role Separation & Least Privilege

In production, database interactions adhere to strict role separation:
- **`postgres` (Superuser / Migration Role):** Used exclusively by Alembic during continuous deployment migrations. Table owner with DDL privileges.
- **`clinic_app_user` (Application Runtime Role):** The FastAPI connection pool connects using this least-privilege role. It has DML permissions (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) on clinic tables but NO DDL permissions (`CREATE`, `DROP`, `ALTER`).

---

## 4. Row Level Security (RLS) Policies

All 28 tables have Row Level Security enabled. When accessing PostgreSQL via Supabase Auth or direct API calls with runtime claims:
- Patients can only view and insert their own records or family members linked to their `account_id`.
- Doctors can only view appointments and medical files for patients assigned to them.
- Reception has access to demographic data, queue operations, and welfare requests, but cannot inspect clinical diagnoses, visits, or prescriptions.
- Manager and Accountant roles have access to clinic ledger and financial reports.
- System infrastructure tables (`password_reset_otps`, `rate_limit_entries`, `outbox_events`) are accessible only by authorized administrative roles.
