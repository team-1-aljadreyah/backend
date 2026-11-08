# Automated Testing & Verification Guide

This document details the test framework, test suites, execution procedures, and verification criteria for the Al-Jadreyah Clinic backend.

---

## 1. Test Architecture & Harness

The test suite uses **pytest** with `pytest-asyncio` and `httpx.ASGITransport` to perform end-to-end API testing without requiring an active external network or running web server.

### Isolation Strategy
- Each test run generates a unique, isolated SQLite database (`test_suite_<pid>.db`) initialized with all database tables and seed configurations.
- Real production Supabase credentials are systematically excluded from destructive tests.
- Real Qi Card financial transactions are simulated or validated against the sandbox specification without moving real capital.

---

## 2. Test Suite Structure

| Test File | Focus Area | Key Invariants Verified |
| --------- | ---------- | ----------------------- |
| `test_appointment_concurrency.py` | Concurrency & Race Conditions | 20 simultaneous bookings to same slot (1 succeeds, 19 fail with 409 `slot_taken`). Slot freed on cancel. Idempotency replay. |
| `test_appointments_and_queues.py` | Booking & Queue Operations | Doctor schedule slots, staff assisted booking, patient check-in, queue ticket issuance. |
| `test_audit_comprehensive.py` | Clinical & Financial Audits | Patient merge history preservation, financial ledger integrity, stock adjustment logs. |
| `test_auth_and_security.py` | Authentication & Crypto | Argon2id verification, legacy hash upgrade, JWT HS256 algorithm enforcement, refresh rotation. |
| `test_clinical_and_lab.py` | Clinical Encounter & Lab | Doctor consultation flow, diagnosis recording, prescription generation, lab order sample entry & confirmation. |
| `test_concurrency_and_idempotency.py` | Idempotency & Concurrency | Payment idempotency, inventory decrement serialization, duplicate walk-in handling. |
| `test_finance_and_accounting.py` | Invoices & Ledgers | Invoice line generation, cash payments, end-of-shift drawer reconciliation, expense tracking. |
| `test_patient_privacy_and_features.py` | Patient Privacy & Features | Reception medical file privacy block, doctor appointment access restriction, three-part name validation, forgot password SMS OTP. |
| `test_pharmacy_and_inventory.py` | Pharmacy & Stock | Medication stock moves, prescription dispensing, low inventory alerts. |
| `test_online_payments_and_welfare.py` | Qi Payments & Welfare | Online payment sessions, social welfare request review & discount calculation, settlement hooks. |
| `test_qi_card_sandbox_contract.py` | Official Qi Sandbox Contract | HTTP Basic Auth, `X-Terminal-Id`, Decimal formatting, RSA-SHA256 signature verification over canonical string, status check fallback. |
| `test_realtime_outbox_multiworker.py` | Real-Time PostgreSQL Outbox | Multi-worker single-use tickets (`realtime_connection_tickets`), transactional outbox rollback on error, cursor fan-out. |
| `test_file_authorization_security.py` | Medical Document Security | Signed HMAC/JWT download tokens (`?token=...`), unauthenticated download rejection (401), cross-patient IDOR protection (403), path traversal rejection (400). |
| `test_redis_free_architecture.py` | Zero Redis Verification | Confirms application boots and operates with zero Redis connection attempts or dependencies. |

---

## 3. Running Tests

### Execute All Tests
```bash
pytest -v
```

### Execute Specific Test Category
```bash
# Run real-time and outbox tests
pytest -v tests/test_realtime_outbox_multiworker.py

# Run Qi Card sandbox contract tests
pytest -v tests/test_qi_card_sandbox_contract.py

# Run file authorization tests
pytest -v tests/test_file_authorization_security.py
```

### Code Formatting and Linting
```bash
ruff check app tests
```

---

## 4. Verification Summary

- **Total Test Cases:** 61
- **Passed:** 60
- **Skipped:** 1 (`test_live_supabase_exclusion.py`, which requires live PostgreSQL engine)
- **Failed:** 0
- **Pass Rate:** 100% of applicable tests
