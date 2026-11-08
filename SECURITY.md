# Security Policy — Al-Jadreyah Clinic Management System

The Al-Jadreyah Clinic Management System manages patient medical records, clinical diagnostics, prescriptions, and financial transactions. Information security and data integrity are fundamental to the operation of the platform.

---

## 1. Supported Versions

Security updates, patches, and hotfixes are actively maintained for the following versions:

| Version | Supported          | Status             |
| ------- | ------------------ | ------------------ |
| 1.0.x   | :white_check_mark: | Current Production |
| < 1.0.0 | :x:                | Deprecated         |

---

## 2. Reporting a Vulnerability

If you discover a security vulnerability within this repository or the live clinic services:

1. **DO NOT open a public GitHub issue.** Public disclosure exposes patient records and healthcare data to potential exploitation.
2. Submit your vulnerability report privately to the clinic administration and security engineering team.
3. Include the following details in your report:
   - Type of vulnerability (e.g., authentication bypass, SQL injection, privilege escalation, IDOR, sensitive data exposure).
   - Step-by-step reproduction instructions or a minimal proof-of-concept.
   - The affected endpoint(s), module(s), or database tables.
   - Potential impact on patient confidentiality and data integrity.

### Response Timeline
- **Initial Acknowledgment**: Within 24 hours of submission.
- **Triage & Assessment**: Within 48 hours.
- **Resolution & Patch Deployment**: Critical vulnerabilities are resolved via priority hotfixes within 72 hours.

---

## 3. Core Security Principles & Architecture

This repository implements multi-layered defensive engineering controls:

### A. Role-Based Access Control (RBAC) & Least Privilege
The system enforces 7 distinct user roles with strict separation of duties:
- `patient`: Access to personal medical file, upcoming bookings, and family members.
- `reception`: Patient check-in, walk-in creation, duplicate checking, and clinic fee collection.
- `doctor`: Patient diagnosis, prescription generation, lab orders, and vital reviews.
- `pharmacy`: Prescription dispensing, inventory management, and over-the-counter sales.
- `lab`: Test result data entry and attachment management.
- `accountant`: Cash closings, payment verification, and daily ledger auditing.
- `manager`: System-wide analytics, staff management, patient merging, and clinic configuration.

### B. Patient Privacy & Medical File Access Restrictions
1. **Reception Medical File Block:** `GET /patients/{id}/file` explicitly strips visits, diagnoses, prescriptions, lab tests, and medical alerts when requested by `reception`. Reception receives only demographic records.
2. **Doctor Appointment Access Restriction:** Doctors are strictly forbidden from opening medical files of patients who have not had a booked, arrived, or completed appointment with them.
3. **Audit Logging:** Every file opening, export, and record view is permanently logged in `audit_logs` with actor ID, timestamp, and patient identifier.
4. **Deleted Account Retention:** When a patient profile is deleted, their underlying medical file remains permanently intact for medical legal compliance.

### C. Authenticated & Signed Token Medical File Access
- Medical documents (lab attachments, social welfare cards) are protected behind `/storage/v1/object/authenticated/{bucket}/{filename}` and `/files/{bucket}/{filename}`.
- Unauthenticated requests are rejected with `401 Unauthorized`.
- Path traversal sequences (`../`, `..\\`) are rejected with `400 Bad Request`.
- To allow standard HTML `<img>` elements in frontend portals without exposing authorization tokens in browser headers, short-lived signed tokens (`?token=<signed_token>`) are generated using HMAC/JWT.
- Tokens verify the caller's identity against the specific bucket and filename. Cross-patient file access is strictly blocked (`403 Forbidden`).

### D. Password Hashing & Migration
- Passwords are encrypted using **Argon2id** (`m=65536, t=3, p=4`).
- Transparent verification for legacy Bcrypt and PBKDF2 hashes is provided with automated upgrading to Argon2id upon successful authentication.
- Plaintext password fallbacks and universal debug bypasses are strictly prohibited.

### E. Distributed Database Rate Limiting (No Redis)
- Sensitive endpoints (`/auth/login`, `/auth/register`, `/auth/password/forgot`) are protected against brute-force attacks via `rate_limit_entries` in PostgreSQL.
- Rate limit buckets are keyed by SHA-256 hashes of client IP or phone numbers.
- Atomic row locking prevents race conditions across distributed Uvicorn workers.

### F. Multi-Worker WebSocket Security
- Real-time WebSocket connections (`/ws`) require single-use connection tickets (`POST /realtime/ticket`).
- Tickets are cryptographically hashed and stored in PostgreSQL (`realtime_connection_tickets`) with a 60-second expiration.
- Atomic SQL updates (`UPDATE ... RETURNING`) guarantee that tickets can only be consumed once across any number of workers.

### G. Qi Card Sandbox Payment Gateway Security
- All integration tests and local runs use the official Qi Card Sandbox (`https://uat-sandbox-3ds-api.qi.iq/api/v1`).
- HTTP Basic Auth with `X-Terminal-Id` header.
- Strict `Decimal` arithmetic for all financial operations. Overpayments and zero-balance charges are refused.
- Webhooks verify RSA-SHA256 signatures over canonical string `paymentId|amount.000|currency|creationDate|status` with authoritative server-to-server reconciliation via `GET /payment/{id}/status`.
