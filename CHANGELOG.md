# Changelog — Al-Jadreyah Clinic Management System Backend

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-11-08

### Added
- **Zero-Redis Architecture (PostgreSQL-Only Shared Infrastructure)**:
  - Completely removed Redis dependencies, connections, configurations, and fallbacks.
  - Implemented transactional outbox table `outbox_events` and PostgreSQL trigger `trg_outbox_event_notify` firing `pg_notify('realtime_events', event.id)`.
  - Implemented worker event delivery engine with local cursor tracking and periodic 500ms recovery polling (`REALTIME_POLL_INTERVAL_SECONDS`).
  - Wire real-time domain events across appointments (`appointment.booked`, `appointment.cancelled`, `appointment.rescheduled`, `appointment.checked_in`, `appointment.ticket_issued`, `appointment.walk_in`), clinical visits (`visit.started`, `visit.finished`), doctor updates (`doctor.late`, `doctor.absent`), laboratory (`lab.result_confirmed`), and user notifications (`notification.created`).
  - Minimal, privacy-preserving event payloads containing only identifiers, timestamps, queue numbers, and status.
- **Multi-Worker WebSocket Ticket System**:
  - Replaced in-memory tickets with database-backed `realtime_connection_tickets`.
  - Cryptographic SHA-256 token hashing with 60-second expiration.
  - Multi-worker atomic consumption via SQL `UPDATE ... RETURNING`, eliminating multi-worker connection rejection (code 4001) and replay attacks.
- **Official Qi Card Sandbox Integration**:
  - Implemented official sandbox client (`https://uat-sandbox-3ds-api.qi.iq/api/v1`) using published test credentials (`paymentgatewaytest` / `WHaNFE5C3qlChqNbAzH4` / terminal `237984`).
  - Basic Authentication with `X-Terminal-Id: 237984`.
  - Implemented `POST /payment`, `GET /payment/{id}/status`, `POST /payment/{id}/refund`, and `POST /payment/{id}/cancel`.
  - Enforced strict Python `decimal.Decimal` financial calculations throughout billing and refunds.
  - Automated webhook verification for RSA-SHA256 signatures (`X-Signature`) over canonical string `paymentId|amount.000|currency|creationDate|status` with authoritative server-to-server reconciliation fallback.
- **Authenticated & Signed Token Medical File Authorization**:
  - Secured `GET /storage/v1/object/authenticated/{bucket}/{filename}` and `GET /files/{bucket}/{filename}` with short-lived signed tokens (`?token=...`) or Bearer tokens.
  - Seamless image rendering in standard frontend `<img />` tags for social welfare review and lab attachments.
  - Object-level authorization blocking cross-patient IDOR and unauthorized staff access.
  - Path traversal defense rejecting directory traversal characters.
- **Distributed Database Rate Limiting**:
  - Implemented `rate_limit_entries` in PostgreSQL with sliding-window expiration and atomic row locking.
  - Applied distributed protection to `/auth/login`, `/auth/register`, and `/auth/password/forgot`.
- **Database Migrations & Schema**:
  - Created Alembic migration `0002_realtime_outbox_qi`.
  - Enabled Row Level Security (RLS) and defined security policies for all 9 additional tables (`patient_merges`, `payment_sessions`, `welfare_requests`, `idempotency_records`, `user_sessions`, `password_reset_otps`, `realtime_connection_tickets`, `outbox_events`, `rate_limit_entries`).
- **Comprehensive Automated Test Suite**:
  - Added test suites: `test_redis_free_architecture.py`, `test_qi_card_sandbox_contract.py`, `test_realtime_outbox_multiworker.py`, `test_file_authorization_security.py`.
  - Expanded test coverage to 61 automated test cases with 100% pass rate.

### Changed
- Upgraded password hashing algorithm to **Argon2id** (`m=65536, t=3, p=4`) with transparent legacy hash upgrading.
- Enforced strict Arabic three-part name validation across patient and staff registrations.
- Blocked medical file contents (visits, diagnoses, prescriptions, lab results) from receptionists (`GET /patients/{id}/file`).
- Restricted doctor medical file access strictly to patients with whom they have had appointments.
- Fixed naive vs aware datetime comparisons across all authentication and rate-limiting modules.

---

## [1.0.0] - 2026-11-06

### Added
- **Patient Deduplication & Medical Record Merging**:
  - Arabic name normalization (`normalize_patient_name`) unifying Alef variants, Taa Marbuta, Yaa, and stripping diacritics.
  - Iraqi phone number normalization (`normalize_phone_local`) standardizing formats into `07XXXXXXXXX`.
  - Real-time candidate duplicate detection endpoint `POST /patients/duplicates/check` with multi-tier confidence scoring.
  - Suspicious duplicate cluster review endpoint `GET /patients/duplicates`.
  - Atomic patient record consolidation endpoint `POST /patients/merge` restricted strictly to Clinic Managers.
  - Non-destructive soft-merging preserving source records with `merged_into_patient_id`, `merged_at`, `merged_by`, and `merge_reason`.
  - Transparent pointer resolution for patient files (`GET /patients/{id}/file`) resolving merged IDs to active primary records.
  - Dedicated immutable merge audit log table `patient_merges`.
  - Partial unique index `idx_unique_active_patient_phone_name` preventing concurrent duplicate patient registrations while allowing family members to share phone numbers.
- **Double Booking Prevention & Appointment Concurrency Control**:
  - PostgreSQL GiST Exclusion Constraint `exclude_overlapping_doctor_appointments` using `btree_gist` and `tstzrange` preventing overlapping appointments across active statuses (`booked`, `arrived`, `in_progress`, `done`).
  - Cross-branch doctor scheduling protection preventing simultaneous bookings across multiple physical clinic locations.
  - Slot duration calculations coordinated in canonical clinic timezone (`Asia/Baghdad` / UTC+3).
  - Row-level transaction serialization (`SELECT ... FOR UPDATE`) serializing concurrent booking and rescheduling operations.
  - Atomic rescheduling with deadline verification and slot holding.
- **Scoped Idempotency Control**:
  - Dedicated `idempotency_records` table and `app.core.idempotency` service.
  - Support for `Idempotency-Key` and `X-Idempotency-Key` headers across booking, walk-ins, check-ins, payments, and pharmacy sales.
  - Canonical SHA-256 payload hashing with `409 Conflict` on key reuse with different parameters.
- **Core Clinical & Financial Architecture**:
  - Complete 85+ endpoint REST API with unified response envelope `{ "success": true, "data": ... }`.
  - Multi-tier Role-Based Access Control (RBAC) across 7 distinct roles.
  - Non-destructive financial auditing (reversals, voids, daily cash closings, doctor dues).
  - Qi Payment Gateway sandbox integration with RSA notification verification.
  - Automated test suite comprising 35 comprehensive integration, unit, and concurrency tests.

### Security
- Passwords secured via PBKDF2-HMAC-SHA256 with 100,000 iterations and cryptographic salt.
- JWT session management with short-lived access tokens and refresh token rotation.
- Protected multi-part medical document storage with short-lived signed URLs.
