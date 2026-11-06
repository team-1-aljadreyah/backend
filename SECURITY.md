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

### A. Role-Based Access Control (RBAC) & Principle of Least Privilege
The system enforces 7 distinct user roles with strict separation of duties:
- `patient`: Access to personal medical file, upcoming bookings, and family members.
- `reception`: Patient check-in, walk-in creation, duplicate checking, and clinic fee collection.
- `doctor`: Patient diagnosis, prescription generation, lab orders, and vital reviews.
- `pharmacy`: Prescription dispensing, inventory management, and over-the-counter sales.
- `lab`: Test result data entry and attachment management.
- `accountant`: Cash closings, payment verification, and daily ledger auditing.
- `manager`: System-wide analytics, staff management, patient merging, and clinic configuration.

### B. Authentication & Session Security
- **Passwords**: Hashed with PBKDF2-HMAC-SHA256 (100,000 rounds) and random salt.
- **Tokens**: Short-lived JWT access tokens signed with HS256 combined with secure refresh token rotation.
- **Normalization**: Phone numbers are normalized into canonical Iraqi local format (`07XXXXXXXXX`) to eliminate credential collision.

### C. Concurrency, Race Condition & Idempotency Controls
- **Exclusion Constraints**: Database-level PostgreSQL GiST exclusion constraint (`exclude_overlapping_doctor_appointments`) prevents double-booking across all branches and active statuses.
- **Transaction Serialization**: Row-level locking (`SELECT ... FOR UPDATE`) prevents concurrent booking races and duplicate patient merges.
- **Idempotency Keys**: Supported via `Idempotency-Key` or `X-Idempotency-Key` headers with canonical SHA-256 payload hashing to prevent double-charges and replay attacks.

### D. Financial Auditability & Data Protection
- **Non-Destructive Accounting**: Financial records (`payments`, `expenses`) cannot be hard-deleted from the database. Adjustments require explicit reversal or voiding transactions accompanied by mandatory audit justifications.
- **Audit Logging**: Sensitive system operations (`patient.merge`, `file.open`, `appointment.cancel`, `prescription.dispense`) are logged into an immutable `audit_logs` table.

---

## 4. Responsible Disclosure Guidelines

- Do not attempt to access, modify, or download real patient medical records during vulnerability assessments.
- Avoid Denial of Service (DoS) or Resource Exhaustion attacks against production infrastructure.
- Provide sufficient time for the maintenance team to deploy patches before disclosing any findings publicly.
