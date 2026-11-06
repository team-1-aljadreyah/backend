<div align="center">

# 🏥 Al-Jadreyah Clinic Management System — Backend API

**A high-concurrency, production-grade healthcare management backend engineered with Python, FastAPI, SQLAlchemy 2.0, and PostgreSQL.**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Supabase](https://img.shields.io/badge/Supabase-Ready-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com/)
[![Tests](https://img.shields.io/badge/Tests-35%20Passed-success?logo=pytest&logoColor=white)](tests/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![License](https://img.shields.io/badge/License-Proprietary-red)](#19-license)

</div>

---

## 1. Overview

The **Al-Jadreyah Clinic Management System Backend** is an enterprise-grade medical information system designed for multi-specialty polyclinics and outpatient medical centers. The backend orchestrates patient registration, electronic health records (EHR), clinical consultations, digital prescriptions, lab orders, pharmacy inventory, queue management, and accounting.

### Problem It Solves
- **Eliminates Accidental Patient Duplication**: Identifies duplicate patient candidates using normalized Arabic name matching and phone normalization, enabling managers to merge fragmented medical histories atomically into a single unified record without data loss.
- **Prevents Double Booking at the Database Engine Level**: Enforces mathematical guarantees via PostgreSQL **GiST Exclusion Constraints** preventing overlapping appointments across doctors and branches, ensuring zero race conditions even under concurrent load.
- **Audit-Compliant Financial Governance**: Replaces destructive deletes with immutable ledger transactions (reversals, voids, daily cash closings) preserving an untampered financial audit trail.
- **End-to-End Clinical Flow**: Coordinates patient arrival, reception check-in, triage vitals, consultation notes, laboratory order fulfillment, prescription dispensing, and automated queue TV display.

---

## 2. Key Capabilities

### 🔍 Patient Deduplication & Medical Record Merging
- **Arabic Name Normalization**: Canonicalizes Alef variants (`أ/إ/آ/ٱ` $\rightarrow$ `ا`), Taa Marbuta (`ة` $\rightarrow$ `ه`), Yaa (`ى/ئ` $\rightarrow$ `ي`), strips diacritics/tashkeel, and eliminates redundant whitespace.
- **Iraqi Phone Normalization**: Normalizes domestic and international phone numbers (`+964`, `00964`, `964`, local `7...`) into canonical Iraqi format `07XXXXXXXXX`.
- **Candidate Duplicate Detection**: Evaluates incoming registrations in real-time (`POST /patients/duplicates/check`), distinguishing exact duplicates from family members sharing the same phone number.
- **Atomic Record Merge**: Managers can merge a duplicate patient record into a primary record (`POST /patients/merge`). Foreign keys across appointments, clinical visits, vital signs, lab orders, and welfare requests are atomically updated, while the source record is non-destructively soft-merged.
- **Transparent Pointer Resolution**: Any historical request for a merged patient ID (`GET /patients/{id}/file`) automatically resolves to the unified primary medical record.

### ⏱️ Double Booking Prevention & Appointment Concurrency Control
- **PostgreSQL GiST Exclusion Constraints**: Utilizes PostgreSQL `btree_gist` extension and range type `tstzrange(start_time, end_time, '[)')` to strictly disallow overlapping appointment intervals for the same doctor across active statuses (`booked`, `arrived`, `in_progress`, `done`).
- **Cross-Branch Scheduling**: Enforces doctor scheduling boundaries globally, preventing a doctor from having overlapping appointments across multiple physical branches.
- **Baghdad Timezone Operations**: Calculates start and end timestamps in `Asia/Baghdad` (UTC+3) based on doctor consultation lengths (`new_minutes` vs. `followup_minutes`).
- **Row-Level Transaction Serialization**: Uses `SELECT ... FOR UPDATE` row locks to serialize high-concurrency booking and rescheduling transactions.
- **Scoped Idempotency Control**: Dedicated idempotency engine supporting `Idempotency-Key` and `X-Idempotency-Key` headers with canonical SHA-256 payload hashing to prevent duplicate bookings, double-charges, and replay requests.

### 🩺 Clinical Consultation & EHR
- Complete diagnosis logging, internal doctor notes, and digital prescriptions with dosage and frequency instructions.
- Real-time patient medical alerts (allergies, chronic conditions, blood type).
- Triage vital signs recording (blood pressure, pulse, temperature, SpO2, height, weight).
- Diagnostic laboratory order management with status workflow (`requested` $\rightarrow$ `entered` $\rightarrow$ `confirmed`) and result payloads.

### 💊 Pharmacy & Inventory Control
- Real-time medicine stock tracking with low-inventory and expiration warnings.
- Prescription dispensing workflow with automated stock decrement.
- Over-the-counter (OTC) pharmacy point-of-sale with immutable stock move logging.

### 💳 Financial Management & Qi Card Gateway
- Itemized patient invoice generation for doctor visits, diagnostic tests, and procedures.
- Non-destructive payment reversals and expense voids requiring mandatory audit justifications.
- Reception daily cash shift summaries and accountant end-of-day closings.
- Doctor dues and revenue share calculation (`clinic_percent` vs. `service_percent`).
- Qi Payment Gateway integration with payment sessions, return callbacks, and RSA signature verification.

### 📺 Waiting Queue & Public TV Screen
- Automated ticket generation (`A-001`, `B-002`) by doctor.
- Public display screen endpoint (`GET /public/queue-screen`) powering waiting room TV monitors with real-time room status, next tickets, and doctor delay notices.

---

## 3. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Language** | Python 3.12 | Modern type-hinted runtime |
| **Framework** | FastAPI 0.115+ | High-performance asynchronous web framework |
| **Data Validation** | Pydantic v2 & Pydantic Settings | Strict schema definition and environment configuration |
| **Database Engine** | PostgreSQL 16+ / Supabase | Relational storage with GiST exclusion constraints & RLS |
| **ORM / Query Builder** | SQLAlchemy 2.0 (asyncio) + asyncpg | Fully asynchronous connection pooling and ORM queries |
| **Prototyping DB** | SQLite + aiosqlite | Fast, isolated automated unit test execution |
| **Security & Auth** | PyJWT, Passlib, Bcrypt | PBKDF2 password hashing and HS256 JWT sessions |
| **Server Engine** | Uvicorn (standard) | ASGI production server |
| **Testing** | Pytest, Pytest-Asyncio, HTTPX | Automated integration, concurrency, and unit test suites |
| **Containerization** | Docker, Docker Compose | Production-grade containerization and local stack orchestration |

---

## 4. Architecture & Project Structure

The project adheres to a clean, modular layer-separated architecture with strict separation of concerns:

```
backend/
├── app/
│   ├── api/
│   │   └── routes/             # REST route controllers (21 modules, 85+ endpoints)
│   │       ├── appointments.py # Booking, rescheduling, check-in, walk-ins, vitals
│   │       ├── audit.py        # System audit logs
│   │       ├── auth.py         # Login, registration, token refresh, password management
│   │       ├── cash.py         # Reception shift summaries & daily closings
│   │       ├── doctors.py      # Working days, slots, queues, absences, delays
│   │       ├── expenses.py     # Clinic operational expenses & voiding audit
│   │       ├── health.py       # Container health check probe (/health)
│   │       ├── invoices.py     # Patient invoices & fee itemization
│   │       ├── lab.py          # Lab orders, test results, file attachments
│   │       ├── ledger.py       # Accounting general ledger
│   │       ├── manager.py      # Longitudinal analytics & clinic overview
│   │       ├── me.py           # Patient profile, family management, ratings
│   │       ├── patients.py     # Patient search, files, duplicate checking & merging
│   │       ├── payments.py     # Cash/online payments & Qi payment gateway
│   │       ├── pharmacy.py     # Inventory catalog, stock receiving, OTC sales
│   │       ├── prescriptions.py# Doctor prescriptions & pharmacy dispensing
│   │       ├── public.py       # Public doctor list & waiting room TV screen
│   │       ├── reports.py      # Doctor dues & monthly financial reports
│   │       ├── services.py     # Medical diagnostic pricing catalog
│   │       ├── settings.py     # Global clinic settings (cancel hours, deposits)
│   │       └── users.py        # Staff user administration
│   ├── core/
│   │   ├── config.py           # Pydantic v2 application configuration
│   │   ├── dependencies.py     # Fast-fail authentication & DB session dependency injection
│   │   ├── envelope.py         # Standard success and error response wrappers
│   │   ├── exceptions.py       # Domain-specific HTTP exception hierarchy
│   │   ├── idempotency.py      # Idempotency key tracking & canonical payload hashing
│   │   ├── logging.py          # Structured operational logging
│   │   ├── permissions.py      # Role-Based Access Control (RBAC) guards
│   │   └── security.py         # PBKDF2 hashing, JWT signing, phone/name normalization
│   ├── database/
│   │   ├── base.py             # SQLAlchemy DeclarativeBase and universal BigInteger PKs
│   │   ├── connection.py       # Async engine & PgBouncer connection pool manager
│   │   └── models/             # Domain relational models (SQLAlchemy 2.0 mapped)
│   │       ├── appointment.py  # Appointments & exclusion indexes
│   │       ├── finance.py      # Invoices, payments, expenses, cash closings
│   │       ├── governance.py   # Settings, audit logs, notifications, idempotency
│   │       ├── patient.py      # Patients, merges, vitals, welfare requests
│   │       ├── pharmacy.py     # Stock items, inventory moves, sales
│   │       ├── profile.py      # User profiles, doctors, clinic branches
│   │       └── visit.py        # Clinical visits, lab orders, medical services
│   ├── integrations/
│   │   ├── payment_provider.py # Qi Card / Mock payment provider gateway
│   │   ├── supabase_auth.py    # Supabase authentication integration
│   │   └── supabase_storage.py # Private medical document uploads & signed URLs
│   ├── schemas/                # Pydantic v2 request and response contracts
│   ├── services/               # Business logic, validation, and multi-table orchestration
│   └── main.py                 # FastAPI application factory, CORS, exception handlers
├── database/
│   └── schema.sql              # SINGLE SOURCE OF TRUTH: Complete PostgreSQL DDL & seeds
├── docs/                       # Comprehensive technical documentation & guides
├── scripts/                    # Operational utilities (migrations, benchmarks, diagnostics)
├── tests/                      # Automated test suite (35+ test cases)
├── .dockerignore               # Docker build file exclusions
├── .editorconfig               # Cross-editor formatting specifications
├── .env.example                # Documented environment variable template
├── .gitattributes              # Git line ending normalization rules
├── .gitignore                  # Production Git ignore specifications
├── .python-version             # Python version pin (3.12.0)
├── CHANGELOG.md                # Version release history (Keep a Changelog)
├── CONTRIBUTING.md             # Contribution guidelines & coding conventions
├── Dockerfile                  # Multi-stage production container build
├── docker-compose.yml          # Containerized local PostgreSQL & API stack
├── pyproject.toml              # Project metadata, build system & tool configurations
├── requirements.txt            # Locked application and testing dependencies
└── SECURITY.md                 # Vulnerability disclosure policy & security controls
```

---

## 5. Prerequisites

Before installing the backend, ensure you have:

- **Python 3.12+** installed on your system (`python --version`).
- **PostgreSQL 16+** (Local PostgreSQL, Docker container, or Supabase project).
  - Required PostgreSQL extension: `btree_gist` (installed automatically via `schema.sql`).
- **Git** for version control.
- **Docker & Docker Compose** (optional, for containerized local execution).

---

## 6. Installation & Setup

### A. Clone the Repository
```bash
git clone https://github.com/your-username/al-jadreyah-backend.git
cd al-jadreyah-backend
```

### B. Create and Activate Virtual Environment

**Linux / macOS:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### C. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### D. Configure Environment Variables
Copy the template configuration file:
```bash
cp .env.example .env
```
Edit `.env` with your preferred text editor and configure your database credentials and secret key:
```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgrespassword@localhost:5432/aljadreyah_clinic
SECRET_KEY=generate-a-secure-random-key-at-least-32-chars-long
APP_TIMEZONE=Asia/Baghdad
```

### E. Initialize Database Schema
To initialize a fresh PostgreSQL database with the complete schema, exclusion constraints, indexes, triggers, and initial seed data, execute `database/schema.sql`:

**Using `psql` (Local or Remote PostgreSQL):**
```bash
psql "postgresql://postgres:postgrespassword@localhost:5432/aljadreyah_clinic" -f database/schema.sql
```

**Using Supabase Web Dashboard:**
Open your Supabase Project $\rightarrow$ **SQL Editor** $\rightarrow$ Paste the contents of [`database/schema.sql`](database/schema.sql) $\rightarrow$ Click **Run**.

---

## 7. Running the Application

### Development Mode (with Live Reload)
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production Mode
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The application will initialize and serve traffic at `http://localhost:8000`.

---

## 8. Interactive API Documentation

When the application is running, comprehensive interactive OpenAPI documentation is automatically available:

- **Swagger UI**: [`http://localhost:8000/docs`](http://localhost:8000/docs)
- **ReDoc**: [`http://localhost:8000/redoc`](http://localhost:8000/redoc)
- **OpenAPI Schema (JSON)**: [`http://localhost:8000/openapi.json`](http://localhost:8000/openapi.json)

### Available API Modules Overview

| Tag | Prefix / Path | Key Endpoints | Description |
|---|---|---|---|
| **Auth** | `/auth` | `/login`, `/register`, `/refresh`, `/password/*` | Authentication, JWT sessions, password reset & change |
| **Public** | `/public` | `/doctors`, `/queue-screen` | Public doctor directory & waiting room TV monitor |
| **Me** | `/me` | `/profile`, `/family`, `/appointments`, `/ratings` | Patient personal portal, family members, appointments |
| **Doctors** | `/doctors` | `/{id}/days`, `/{id}/slots`, `/schedules` | Doctor schedules, shift hours, availability slot calculation |
| **Appointments** | `/appointments` | `/`, `/by-staff`, `/{id}/cancel`, `/{id}/check-in` | Slot reservation, walk-ins, triage vitals, rescheduling |
| **Patients** | `/patients` | `/{id}/file`, `/duplicates/check`, `/merge` | Medical records, duplicate candidate detection, record merge |
| **Clinical** | `/appointments` | `/{id}/start`, `/{id}/finish`, `/{id}/vitals` | Consultations, clinical diagnoses, medical history |
| **Lab** | `/lab` | `/orders`, `/orders/{id}/results`, `/upload` | Lab diagnostic orders, entering results, file attachments |
| **Prescriptions** | `/prescriptions` | `/`, `/{id}/dispense` | Digital prescriptions, dosage instructions, pharmacy dispensing |
| **Pharmacy** | `/pharmacy` | `/catalog`, `/stock`, `/sales` | Medicine inventory, stock movements, OTC sales |
| **Finance** | `/invoices`, `/cash` | `/invoices/today`, `/cash/shift-summary`, `/cash/close` | Daily patient invoices, cash drawers, shift handovers |
| **Payments** | `/payments` | `/{id}`, `/appointments/{id}/payments`, `/reversals` | Cash/online payments, Qi Card gateway, payment reversals |
| **Expenses** | `/expenses` | `/`, `/{id}/void` | Operational clinic expenses & voiding audit |
| **Ledger** | `/ledger` | `/` | Double-entry unified accounting ledger |
| **Reports** | `/reports` | `/doctor-dues`, `/monthly` | Doctor dues, clinic revenue share, financial summaries |
| **Manager** | `/manager` | `/overview`, `/analytics` | Clinic analytics, occupancy, revenue by specialty |
| **Users** | `/users` | `/`, `/{id}/enable`, `/{id}/disable` | Staff user administration & account status |
| **Settings** | `/settings` | `/` | Clinic parameters (cancellation deadline, deposit threshold) |
| **Services** | `/services` | `/` | Medical services & diagnostic test pricing catalog |
| **Audit** | `/audit` | `/` | Immutable administrative & security audit logs |
| **Health** | `/health` | `/health` | Uptime and readiness probe for Docker / Cloud Run |

---

## 9. Authentication & Security

### Role-Based Access Control (RBAC) Matrix
The system strictly enforces the principle of least privilege across 7 roles:

| Domain / Resource | Patient | Reception | Doctor | Pharmacy | Lab | Accountant | Manager |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Personal File & Family** | :white_check_mark: | :x: | :x: | :x: | :x: | :x: | :x: |
| **Book Own Appointment** | :white_check_mark: | :x: | :x: | :x: | :x: | :x: | :x: |
| **Walk-ins & Check-in** | :x: | :white_check_mark: | :x: | :x: | :x: | :x: | :white_check_mark: |
| **Duplicate Candidate Check** | :x: | :white_check_mark: | :x: | :x: | :x: | :x: | :white_check_mark: |
| **Patient Record Merge** | :x: | :x: | :x: | :x: | :x: | :x: | :white_check_mark: |
| **Patient Medical File** | :x: | :white_check_mark: | :white_check_mark: | :x: | :x: | :x: | :white_check_mark: |
| **Clinical Diagnosis & Notes** | :x: | :x: | :white_check_mark: | :x: | :x: | :x: | :white_check_mark: |
| **Prescription Dispensing** | :x: | :x: | :x: | :white_check_mark: | :x: | :x: | :white_check_mark: |
| **Medicine Inventory & Sales** | :x: | :x: | :x: | :white_check_mark: | :x: | :x: | :white_check_mark: |
| **Lab Results Entry** | :x: | :x: | :x: | :x: | :white_check_mark: | :x: | :white_check_mark: |
| **Cash Drawer & Closings** | :x: | :white_check_mark: | :x: | :x: | :x: | :white_check_mark: | :white_check_mark: |
| **Ledger & Financial Reports**| :x: | :x: | :x: | :x: | :x: | :white_check_mark: | :white_check_mark: |
| **System Settings & Audit** | :x: | :x: | :x: | :x: | :x: | :x: | :white_check_mark: |

---

## 10. Database Schema & Concurrency Design

All relational structures, constraints, indexes, RLS policies, and triggers are defined in a single, unified file: [`database/schema.sql`](database/schema.sql).

### Key Relational Protections
1. **Double Booking Exclusion Constraint**:
   ```sql
   ALTER TABLE appointments
   ADD CONSTRAINT exclude_overlapping_doctor_appointments
   EXCLUDE USING gist (
       doctor_id WITH =,
       tstzrange(start_time, end_time, '[)') WITH &&
   )
   WHERE (status IN ('booked', 'arrived', 'in_progress', 'done') AND start_time IS NOT NULL AND end_time IS NOT NULL);
   ```
2. **Concurrent Duplicate Patient Registration Protection**:
   ```sql
   CREATE UNIQUE INDEX idx_unique_active_patient_phone_name
   ON patients (normalized_phone, normalized_name)
   WHERE merged_into_patient_id IS NULL;
   ```
3. **Non-Destructive Financial Auditing**:
   - `payments` and `expenses` tables use transactional reversals (`kind = 'reversal'`, `is_void = true`) with mandatory `reason` fields.
4. **Automated `updated_at` Triggers**:
   - PostgreSQL triggers automatically update timestamps on every row modification across all operational tables.

---

## 11. Testing & Verification

The repository includes a comprehensive automated test suite verifying every domain, integration, and concurrency scenario.

### Running All Tests
```bash
pytest -v
```

### Running Specific Test Suites
```bash
# 20 concurrent booking requests and idempotency tests
pytest tests/test_appointment_concurrency.py -v

# Patient deduplication, name normalization, and record merge tests
pytest tests/test_patient_merge_and_dedup.py -v

# Authentication, RBAC, and security tests
pytest tests/test_auth_and_security.py -v

# Financial ledger, cash closings, and payment reversals
pytest tests/test_finance_and_accounting.py -v

# Pharmacy inventory and OTC sales
pytest tests/test_pharmacy_and_inventory.py -v

# Clinical consultations and laboratory flows
pytest tests/test_clinical_and_lab.py -v
```

### Code Formatting & Linting
```bash
# Check code style and syntax with Ruff
ruff check .

# Format code
ruff format .
```

---

## 12. Docker & Containerization

### Running with Docker Compose (Recommended for Local Stack)
The project includes a ready-to-run `docker-compose.yml` that orchestrates both PostgreSQL 16 and the FastAPI application:

```bash
docker compose up --build
```
This automatically boots PostgreSQL on port `5432`, initializes `schema.sql`, builds the FastAPI container, and exposes the API on `http://localhost:8000`.

### Building and Running the Standalone Docker Image
```bash
# Build production image
docker build -t aljadreyah-backend:latest .

# Run container
docker run -d \
  --name aljadreyah-api \
  -p 8000:8000 \
  --env-file .env \
  aljadreyah-backend:latest
```

### Health Check Endpoint
The Dockerfile includes an automated health probe:
```bash
curl http://localhost:8000/health
```
```json
{
  "status": "healthy",
  "app": "Al-Jadreyah Clinic Management System",
  "environment": "production",
  "timestamp": "2026-11-06T14:20:00.000000+00:00"
}
```

---

## 13. Environment Variables Reference

| Variable | Description | Required | Default Value |
|---|---|:---:|---|
| `APP_NAME` | Display name of the application | No | `"Al-Jadreyah Clinic Management System"` |
| `APP_ENV` | Environment mode (`development`, `testing`, `production`) | No | `"development"` |
| `APP_DEBUG` | Enables FastAPI debug traceback mode | No | `false` |
| `APP_HOST` | Network interface address to bind Uvicorn | No | `"0.0.0.0"` |
| `APP_PORT` | Port number to bind Uvicorn | No | `8000` |
| `APP_TIMEZONE` | Clinic operational timezone | No | `"Asia/Baghdad"` |
| `SECRET_KEY` | Cryptographic secret for signing tokens | **Yes** | *None (Must be set)* |
| `DATABASE_URL` | Async PostgreSQL/SQLite database connection URL | **Yes** | `"sqlite+aiosqlite:///./clinic.db"` |
| `DB_ECHO` | Logs SQL queries to stdout | No | `false` |
| `DB_POOL_SIZE` | SQLAlchemy connection pool size | No | `15` |
| `DB_MAX_OVERFLOW` | Maximum overflow connections above pool size | No | `15` |
| `SUPABASE_URL` | Supabase project API URL | Optional | `None` |
| `SUPABASE_ANON_KEY` | Supabase anonymous/publishable key | Optional | `None` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role secret key | Optional | `None` |
| `SUPABASE_STORAGE_BUCKET` | Bucket name for private medical files | No | `"lab-results"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifespan in minutes | No | `1440` (24h) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifespan in days | No | `30` |
| `ALGORITHM` | JWT signing algorithm | No | `"HS256"` |
| `FRONTEND_ORIGINS` | Comma-separated list of allowed CORS origins | No | `http://localhost:3000` |
| `LOG_LEVEL` | Log severity threshold (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | No | `"INFO"` |
| `PAYMENT_PROVIDER_MODE` | Payment mode (`mock` or `qi`) | No | `"mock"` |
| `PAYMENT_GATEWAY_API_KEY` | Payment gateway API token | Optional | `None` |

---

## 14. Response Envelope & Error Handling

All API endpoints return a standardized JSON response envelope matching the frontend contract:

### Success Response (`200 OK`, `201 Created`)
```json
{
  "success": true,
  "data": {
    "appointment_id": 42,
    "status": "booked"
  }
}
```

### Error Response (`400`, `401`, `403`, `404`, `409`, `422`, `429`)
```json
{
  "success": false,
  "code": "slot_taken",
  "message": "This time slot is already taken",
  "errors": {}
}
```

### Common Error Codes
- `slot_taken`: Appointment time slot is already reserved.
- `idempotency_conflict`: Idempotency key reused with different request payload.
- `day_off`: Doctor does not work on the specified date or shift.
- `too_late`: Attempted cancellation or rescheduling within the non-changeable deadline.
- `deposit_required`: Patient account requires an upfront deposit due to excessive past no-shows.
- `wrong_password`: Current password incorrect (returns HTTP 422 to prevent signing out the user).
- `self_merge_not_allowed`: Cannot merge a patient record into itself.
- `patient_already_merged`: The patient record has already been consolidated.

---

## 15. Development Guidelines

When contributing new capabilities to this repository:
1. **Adding an Endpoint**: Create or update the router in `app/api/routes/`, define request/response models in `app/schemas/`, and implement business logic in `app/services/`.
2. **Database Changes**: Update [`database/schema.sql`](database/schema.sql) first (it is the single source of truth), then update the SQLAlchemy model in `app/database/models/`.
3. **Testing**: Add an automated test in `tests/` verifying happy path, validation failures, and unauthorized access attempts.
4. **Idempotency**: Any non-idempotent create or pay operation should accept `Idempotency-Key` / `X-Idempotency-Key` and leverage `app.core.idempotency`.

---

## 16. Contributing

Please review [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines, branch naming conventions, commit standards, and the pull request checklist.

---

## 17. Security Disclosure

Please review [SECURITY.md](SECURITY.md) for our vulnerability disclosure policy and information on how to report security vulnerabilities responsibly.

---

## 18. CI/CD Pipeline

Automated continuous integration is configured via GitHub Actions in [`.github/workflows/ci.yml`](.github/workflows/ci.yml). On every push and pull request to `main`, the pipeline automatically:
1. Checks out the code and sets up Python 3.12.
2. Installs production and development dependencies.
3. Validates Python syntax and bytecode compilation across all modules.
4. Runs linting and static analysis using Ruff.
5. Executes the full automated test suite with Pytest.

---

## 19. License

This project is proprietary software developed for the **Al-Jadreyah Clinic Management System**. All rights reserved. Unauthorized copying, modification, distribution, or deployment of this software without explicit written permission from the clinic administration is strictly prohibited.

---

## 20. Author & Project Information

- **Project**: Al-Jadreyah Clinic Management System — Backend API
- **Maintained by**: Al-Jadreyah Clinic Backend Engineering Team
- **Repository**: [al-jadreyah-backend](https://github.com/your-username/al-jadreyah-backend)
- **Status**: Production Stable (v1.0.0)
