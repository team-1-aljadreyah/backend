# Changelog — Al-Jadreyah Clinic Management System Backend

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
