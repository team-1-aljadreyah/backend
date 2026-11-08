-- =============================================================================
-- Al-Jadreyah Clinic Management System
-- Complete Database Initialization Script (Single Source of Truth)
-- File: backend/database/schema.sql
-- Database: Supabase PostgreSQL (Supports PostgreSQL 15+ / 16+)
-- =============================================================================

-- =============================================================================
-- SECTION 1: EXTENSIONS
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- =============================================================================
-- SECTION 2: CUSTOM ENUM TYPES
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM (
            'patient',
            'reception',
            'doctor',
            'pharmacy',
            'lab',
            'accountant',
            'manager'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'branch_id') THEN
        CREATE TYPE branch_id AS ENUM ('main', 'second');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'shift_type') THEN
        CREATE TYPE shift_type AS ENUM ('morning', 'evening');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'visit_kind') THEN
        CREATE TYPE visit_kind AS ENUM ('new', 'followup');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'appointment_status') THEN
        CREATE TYPE appointment_status AS ENUM (
            'booked',
            'arrived',
            'in_progress',
            'done',
            'cancelled',
            'no_show'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'cancel_reason') THEN
        CREATE TYPE cancel_reason AS ENUM ('patient', 'doctor_absent', 'unpaid');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'relation_type') THEN
        CREATE TYPE relation_type AS ENUM ('self', 'child', 'parent', 'spouse', 'sibling', 'other');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'blood_type_enum') THEN
        CREATE TYPE blood_type_enum AS ENUM ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'currency_type') THEN
        CREATE TYPE currency_type AS ENUM ('IQD', 'USD');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_method') THEN
        CREATE TYPE payment_method AS ENUM ('cash', 'online');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_kind') THEN
        CREATE TYPE payment_kind AS ENUM ('payment', 'refund', 'reversal');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'service_kind') THEN
        CREATE TYPE service_kind AS ENUM ('test', 'xray', 'procedure');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'lab_status') THEN
        CREATE TYPE lab_status AS ENUM ('requested', 'entered', 'confirmed');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sample_type') THEN
        CREATE TYPE sample_type AS ENUM ('blood', 'urine', 'stool', 'swab', 'other');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'stock_unit') THEN
        CREATE TYPE stock_unit AS ENUM ('tablet', 'capsule', 'bottle', 'tube', 'injection', 'sachet');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'stock_move_kind') THEN
        CREATE TYPE stock_move_kind AS ENUM ('create', 'receive', 'dispense', 'edit', 'sale');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sale_kind') THEN
        CREATE TYPE sale_kind AS ENUM ('prescription', 'counter');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'expense_category') THEN
        CREATE TYPE expense_category AS ENUM (
            'rent',
            'salaries',
            'power',
            'supplies',
            'medicines',
            'maintenance',
            'other'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notification_type_enum') THEN
        CREATE TYPE notification_type_enum AS ENUM (
            'doctor_absent',
            'doctor_late',
            'result_ready',
            'reminder',
            'turn_near',
            'booked',
            'rate_visit',
            'follow_up',
            'result_for_doctor',
            'welfare_submitted',
            'welfare_approved',
            'welfare_rejected'
        );
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_status') THEN
        CREATE TYPE payment_status AS ENUM ('created', 'success', 'failed', 'authentication_failed', 'canceled');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'welfare_status') THEN
        CREATE TYPE welfare_status AS ENUM ('pending', 'approved', 'rejected');
    END IF;
END $$;

-- Implicit casts for PostgreSQL enums to seamlessly interoperate with SQLAlchemy & asyncpg
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'user_role') THEN
        CREATE CAST (character varying AS user_role) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'branch_id') THEN
        CREATE CAST (character varying AS branch_id) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'shift_type') THEN
        CREATE CAST (character varying AS shift_type) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'visit_kind') THEN
        CREATE CAST (character varying AS visit_kind) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'appointment_status') THEN
        CREATE CAST (character varying AS appointment_status) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'cancel_reason') THEN
        CREATE CAST (character varying AS cancel_reason) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'relation_type') THEN
        CREATE CAST (character varying AS relation_type) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'blood_type_enum') THEN
        CREATE CAST (character varying AS blood_type_enum) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'currency_type') THEN
        CREATE CAST (character varying AS currency_type) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'payment_method') THEN
        CREATE CAST (character varying AS payment_method) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'payment_kind') THEN
        CREATE CAST (character varying AS payment_kind) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'service_kind') THEN
        CREATE CAST (character varying AS service_kind) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'lab_status') THEN
        CREATE CAST (character varying AS lab_status) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'sample_type') THEN
        CREATE CAST (character varying AS sample_type) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'stock_unit') THEN
        CREATE CAST (character varying AS stock_unit) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'stock_move_kind') THEN
        CREATE CAST (character varying AS stock_move_kind) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'sale_kind') THEN
        CREATE CAST (character varying AS sale_kind) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'expense_category') THEN
        CREATE CAST (character varying AS expense_category) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'notification_type_enum') THEN
        CREATE CAST (character varying AS notification_type_enum) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'payment_status') THEN
        CREATE CAST (character varying AS payment_status) WITH INOUT AS IMPLICIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_cast c JOIN pg_type s ON c.castsource = s.oid JOIN pg_type t ON c.casttarget = t.oid WHERE s.typname = 'varchar' AND t.typname = 'welfare_status') THEN
        CREATE CAST (character varying AS welfare_status) WITH INOUT AS IMPLICIT;
    END IF;
END $$;

-- =============================================================================
-- SECTION 3: AUTOMATION FUNCTIONS (Updated At Trigger)
-- =============================================================================
CREATE OR REPLACE FUNCTION set_updated_at_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 4: TABLES DEFINITION
-- =============================================================================

-- 4.1 Branches
CREATE TABLE IF NOT EXISTS branches (
    id VARCHAR(16) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    name_ar VARCHAR(128) NOT NULL,
    address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4.2 Doctors
CREATE TABLE IF NOT EXISTS doctors (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    name_ar VARCHAR(128) NOT NULL,
    specialty VARCHAR(128) NOT NULL,
    specialty_ar VARCHAR(128) NOT NULL,
    fee NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (fee >= 0),
    new_minutes INTEGER NOT NULL DEFAULT 20 CHECK (new_minutes BETWEEN 5 AND 120),
    followup_minutes INTEGER NOT NULL DEFAULT 10 CHECK (followup_minutes BETWEEN 5 AND 120),
    clinic_percent NUMERIC(5, 2) NOT NULL DEFAULT 30 CHECK (clinic_percent BETWEEN 0 AND 100),
    service_percent NUMERIC(5, 2) NOT NULL DEFAULT 30 CHECK (service_percent BETWEEN 0 AND 100),
    days JSONB NOT NULL DEFAULT '[]'::jsonb,
    absences JSONB NOT NULL DEFAULT '[]'::jsonb,
    late_date DATE,
    late_minutes INTEGER NOT NULL DEFAULT 0 CHECK (late_minutes >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_doctors_updated_at ON doctors;
CREATE TRIGGER trg_doctors_updated_at
    BEFORE UPDATE ON doctors
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- 4.3 User Profiles
CREATE TABLE IF NOT EXISTS profiles (
    id BIGSERIAL PRIMARY KEY,
    auth_user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    phone VARCHAR(32) UNIQUE NOT NULL,
    password_hash VARCHAR(256),
    role VARCHAR(32) NOT NULL DEFAULT 'patient',
    doctor_id BIGINT REFERENCES doctors(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_profiles_updated_at ON profiles;
CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- 4.4 Patients & Medical Alerts
CREATE TABLE IF NOT EXISTS patients (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    normalized_name VARCHAR(128),
    normalized_phone VARCHAR(32),
    account_id BIGINT REFERENCES profiles(id) ON DELETE SET NULL,
    relation VARCHAR(32) NOT NULL DEFAULT 'self',
    birth_date DATE,
    allergies JSONB NOT NULL DEFAULT '[]'::jsonb,
    conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    blood_type VARCHAR(8),
    merged_into_patient_id BIGINT REFERENCES patients(id) ON DELETE SET NULL,
    merged_at TIMESTAMPTZ,
    merged_by VARCHAR(128),
    merge_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_patients_updated_at ON patients;
CREATE TRIGGER trg_patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_patient_phone_name
    ON patients (normalized_phone, normalized_name)
    WHERE merged_into_patient_id IS NULL;

-- 4.4.1 Patient Merges Audit
CREATE TABLE IF NOT EXISTS patient_merges (
    id BIGSERIAL PRIMARY KEY,
    source_patient_id BIGINT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    target_patient_id BIGINT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    merged_by_id BIGINT NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    merged_by_name VARCHAR(128) NOT NULL,
    merge_reason TEXT NOT NULL,
    records_transferred JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_patient_merges_source ON patient_merges(source_patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_merges_target ON patient_merges(target_patient_id);

-- 4.5 Appointments & Waiting Queue
CREATE TABLE IF NOT EXISTS appointments (
    id BIGSERIAL PRIMARY KEY,
    patient_id BIGINT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    doctor_id BIGINT NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
    date DATE NOT NULL,
    time VARCHAR(8) NOT NULL DEFAULT '',
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    kind VARCHAR(16) NOT NULL DEFAULT 'new',
    branch VARCHAR(16) NOT NULL DEFAULT 'main',
    status VARCHAR(32) NOT NULL DEFAULT 'booked',
    emergency BOOLEAN NOT NULL DEFAULT FALSE,
    arrival_order INTEGER NOT NULL DEFAULT 0,
    ticket INTEGER,
    called_at TIMESTAMPTZ,
    cancel_reason VARCHAR(32),
    pay_by TIMESTAMPTZ,
    idempotency_key VARCHAR(128) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_appointments_updated_at ON appointments;
CREATE TRIGGER trg_appointments_updated_at
    BEFORE UPDATE ON appointments
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- Concurrency protection: prevent concurrent reservations of the exact same active slot for a doctor
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_doctor_active_slot
    ON appointments (doctor_id, date, time)
    WHERE status IN ('booked', 'arrived', 'in_progress', 'done') AND time <> '';

-- Range-based double-booking exclusion constraint across all branches:
DO \$\$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'exclude_overlapping_doctor_appointments'
    ) THEN
        ALTER TABLE appointments
        ADD CONSTRAINT exclude_overlapping_doctor_appointments
        EXCLUDE USING gist (
            doctor_id WITH =,
            tstzrange(start_time, end_time, '[)') WITH &&
        )
        WHERE (status IN ('booked', 'arrived', 'in_progress', 'done') AND start_time IS NOT NULL AND end_time IS NOT NULL);
    END IF;
END \$\$;

-- 4.6 Appointment Vital Signs
CREATE TABLE IF NOT EXISTS appointment_vitals (
    appointment_id BIGINT PRIMARY KEY REFERENCES appointments(id) ON DELETE CASCADE,
    patient_id BIGINT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    systolic NUMERIC(6, 2) CHECK (systolic IS NULL OR (systolic BETWEEN 50 AND 260)),
    diastolic NUMERIC(6, 2) CHECK (diastolic IS NULL OR (diastolic BETWEEN 30 AND 160)),
    temperature NUMERIC(4, 1) CHECK (temperature IS NULL OR (temperature BETWEEN 33 AND 43)),
    pulse INTEGER CHECK (pulse IS NULL OR (pulse BETWEEN 30 AND 220)),
    spo2 NUMERIC(4, 1) CHECK (spo2 IS NULL OR (spo2 BETWEEN 50 AND 100)),
    weight NUMERIC(6, 2) CHECK (weight IS NULL OR (weight BETWEEN 0.5 AND 300)),
    height NUMERIC(6, 2) CHECK (height IS NULL OR (height BETWEEN 30 AND 230)),
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    by VARCHAR(128) NOT NULL,
    CONSTRAINT chk_blood_pressure_pair CHECK (
        (systolic IS NULL AND diastolic IS NULL) OR
        (systolic IS NOT NULL AND diastolic IS NOT NULL AND systolic > diastolic)
    )
);

-- 4.7 Clinical Visits & Consultations
CREATE TABLE IF NOT EXISTS visits (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    patient_id BIGINT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    doctor_id BIGINT NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
    appointment_id BIGINT REFERENCES appointments(id) ON DELETE SET NULL,
    diagnosis TEXT NOT NULL DEFAULT '',
    internal_note TEXT NOT NULL DEFAULT '',
    medicines JSONB NOT NULL DEFAULT '[]'::jsonb,
    dispensed BOOLEAN NOT NULL DEFAULT FALSE,
    follow_up_on DATE,
    rating_stars INTEGER CHECK (rating_stars IS NULL OR (rating_stars BETWEEN 1 AND 5)),
    rating_comment TEXT,
    rating_at TIMESTAMPTZ
);

-- 4.8 Clinic Services (Tests, Imaging, Procedures)
CREATE TABLE IF NOT EXISTS services (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    name_ar VARCHAR(128) NOT NULL,
    kind VARCHAR(16) NOT NULL,
    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0 OR kind = 'discount'),
    currency VARCHAR(8) NOT NULL DEFAULT 'IQD',
    template JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_services_updated_at ON services;
CREATE TRIGGER trg_services_updated_at
    BEFORE UPDATE ON services
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- 4.9 Invoices & Items
CREATE TABLE IF NOT EXISTS invoice_items (
    id BIGSERIAL PRIMARY KEY,
    appointment_id BIGINT NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    label VARCHAR(128) NOT NULL,
    label_ar VARCHAR(128) NOT NULL,
    kind VARCHAR(32) NOT NULL,
    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0 OR kind = 'discount'),
    currency VARCHAR(8) NOT NULL DEFAULT 'IQD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4.10 Payments & Financial Audit Trail
CREATE TABLE IF NOT EXISTS payments (
    id BIGSERIAL PRIMARY KEY,
    appointment_id BIGINT NOT NULL REFERENCES appointments(id) ON DELETE RESTRICT,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(8) NOT NULL DEFAULT 'IQD',
    method VARCHAR(16) NOT NULL DEFAULT 'cash',
    kind VARCHAR(16) NOT NULL DEFAULT 'payment',
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    by VARCHAR(128) NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    ref_id BIGINT REFERENCES payments(id) ON DELETE RESTRICT,
    key VARCHAR(128) UNIQUE
);

-- 4.11 Laboratory Orders & Diagnostic Results
CREATE TABLE IF NOT EXISTS lab_orders (
    id BIGSERIAL PRIMARY KEY,
    visit_id BIGINT NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
    patient_id BIGINT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    doctor_id BIGINT NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
    service_id BIGINT NOT NULL REFERENCES services(id) ON DELETE RESTRICT,
    status VARCHAR(16) NOT NULL DEFAULT 'requested',
    result JSONB,
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ
);

-- 4.12 Pharmacy Inventory & Stock Items
CREATE TABLE IF NOT EXISTS stock_items (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    unit VARCHAR(32) NOT NULL DEFAULT 'tablet',
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    low_level INTEGER NOT NULL DEFAULT 10 CHECK (low_level >= 0),
    expires_on DATE,
    barcode VARCHAR(64) UNIQUE,
    price NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (price >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_stock_items_updated_at ON stock_items;
CREATE TRIGGER trg_stock_items_updated_at
    BEFORE UPDATE ON stock_items
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at_timestamp();

-- 4.13 Stock Movement Log
CREATE TABLE IF NOT EXISTS stock_moves (
    id BIGSERIAL PRIMARY KEY,
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    by VARCHAR(128) NOT NULL,
    kind VARCHAR(32) NOT NULL,
    stock_id BIGINT NOT NULL REFERENCES stock_items(id) ON DELETE RESTRICT,
    item_name VARCHAR(128) NOT NULL,
    unit VARCHAR(32) NOT NULL,
    change INTEGER NOT NULL,
    quantity_after INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);

-- 4.14 Pharmacy Sales (Prescription & Counter)
CREATE TABLE IF NOT EXISTS pharmacy_sales (
    id BIGSERIAL PRIMARY KEY,
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    by VARCHAR(128) NOT NULL,
    kind VARCHAR(32) NOT NULL,
    customer VARCHAR(128) NOT NULL,
    lines JSONB NOT NULL DEFAULT '[]'::jsonb,
    total NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    idempotency_key VARCHAR(128) UNIQUE
);

-- 4.15 Cash Register Closings
CREATE TABLE IF NOT EXISTS cash_closings (
    id BIGSERIAL PRIMARY KEY,
    by VARCHAR(128) NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payments INTEGER NOT NULL DEFAULT 0,
    expected_iqd NUMERIC(14, 2) NOT NULL DEFAULT 0,
    expected_usd NUMERIC(14, 2) NOT NULL DEFAULT 0,
    counted_iqd NUMERIC(14, 2) NOT NULL DEFAULT 0,
    counted_usd NUMERIC(14, 2) NOT NULL DEFAULT 0,
    difference_iqd NUMERIC(14, 2) NOT NULL DEFAULT 0,
    difference_usd NUMERIC(14, 2) NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT ''
);

-- 4.16 Clinic Operational Expenses
CREATE TABLE IF NOT EXISTS expenses (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    category VARCHAR(32) NOT NULL,
    amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(8) NOT NULL DEFAULT 'IQD',
    note TEXT NOT NULL DEFAULT '',
    by VARCHAR(128) NOT NULL,
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    voided_by VARCHAR(128),
    voided_at TIMESTAMPTZ,
    voided_reason TEXT
);

-- 4.17 Clinic Global Settings
CREATE TABLE IF NOT EXISTS clinic_settings (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    cancel_hours INTEGER NOT NULL DEFAULT 3 CHECK (cancel_hours BETWEEN 0 AND 72),
    no_show_limit INTEGER NOT NULL DEFAULT 3 CHECK (no_show_limit BETWEEN 1 AND 10),
    deposit_amount NUMERIC(12, 2) NOT NULL DEFAULT 10000 CHECK (deposit_amount >= 0),
    prescription_days INTEGER NOT NULL DEFAULT 7 CHECK (prescription_days BETWEEN 1 AND 90),
    usd_rate NUMERIC(10, 2) NOT NULL DEFAULT 1310 CHECK (usd_rate > 0),
    welfare_discount_percent NUMERIC(5, 2) NOT NULL DEFAULT 25.0 CHECK (welfare_discount_percent BETWEEN 0 AND 100),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4.18 Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_name VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL,
    action VARCHAR(64) NOT NULL,
    target VARCHAR(256) NOT NULL
);

-- 4.19 User Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    key VARCHAR(128) UNIQUE,
    type VARCHAR(32) NOT NULL,
    params JSONB NOT NULL DEFAULT '{}'::jsonb,
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read BOOLEAN NOT NULL DEFAULT FALSE
);

-- =============================================================================
-- SECTION 5: PERFORMANCE INDEXES
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_profiles_auth_user_id ON profiles(auth_user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_phone ON profiles(phone);
CREATE INDEX IF NOT EXISTS idx_patients_account_id ON patients(account_id);
CREATE INDEX IF NOT EXISTS idx_patients_phone ON patients(phone);
CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(name);

CREATE INDEX IF NOT EXISTS idx_appointments_patient_id ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor_date ON appointments(doctor_id, date);
CREATE INDEX IF NOT EXISTS idx_appointments_date_status ON appointments(date, status);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);

CREATE INDEX IF NOT EXISTS idx_visits_patient_id ON visits(patient_id);
CREATE INDEX IF NOT EXISTS idx_visits_doctor_id ON visits(doctor_id);
CREATE INDEX IF NOT EXISTS idx_visits_created_at ON visits(created_at);

CREATE INDEX IF NOT EXISTS idx_lab_orders_patient_id ON lab_orders(patient_id);
CREATE INDEX IF NOT EXISTS idx_lab_orders_visit_id ON lab_orders(visit_id);
CREATE INDEX IF NOT EXISTS idx_lab_orders_status ON lab_orders(status);

CREATE INDEX IF NOT EXISTS idx_payments_appointment_id ON payments(appointment_id);
CREATE INDEX IF NOT EXISTS idx_payments_at ON payments(at);
CREATE INDEX IF NOT EXISTS idx_payments_ref_id ON payments(ref_id);

CREATE INDEX IF NOT EXISTS idx_stock_items_barcode ON stock_items(barcode);
CREATE INDEX IF NOT EXISTS idx_stock_moves_stock_id ON stock_moves(stock_id);
CREATE INDEX IF NOT EXISTS idx_pharmacy_sales_at ON pharmacy_sales(at);

CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id, read);
CREATE INDEX IF NOT EXISTS idx_audit_logs_at ON audit_logs(at);

-- =============================================================================
-- SECTION 6: ROW LEVEL SECURITY (RLS) HELPER FUNCTIONS
-- =============================================================================
DROP FUNCTION IF EXISTS get_current_profile_id() CASCADE;
CREATE OR REPLACE FUNCTION get_current_profile_id()
RETURNS BIGINT AS $$
    SELECT id FROM profiles WHERE auth_user_id = auth.uid() LIMIT 1;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

DROP FUNCTION IF EXISTS get_current_user_role() CASCADE;
CREATE OR REPLACE FUNCTION get_current_user_role()
RETURNS VARCHAR(32) AS $$
    SELECT role FROM profiles WHERE auth_user_id = auth.uid() LIMIT 1;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

DROP FUNCTION IF EXISTS is_staff() CASCADE;
CREATE OR REPLACE FUNCTION is_staff()
RETURNS BOOLEAN AS $$
    SELECT role IS NOT NULL AND role <> 'patient' FROM profiles WHERE auth_user_id = auth.uid() LIMIT 1;
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- =============================================================================
-- SECTION 7: ROW LEVEL SECURITY (RLS) ACTIVATION & POLICIES
-- =============================================================================
ALTER TABLE branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctors ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointment_vitals ENABLE ROW LEVEL SECURITY;
ALTER TABLE visits ENABLE ROW LEVEL SECURITY;
ALTER TABLE services ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE lab_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_moves ENABLE ROW LEVEL SECURITY;
ALTER TABLE pharmacy_sales ENABLE ROW LEVEL SECURITY;
ALTER TABLE cash_closings ENABLE ROW LEVEL SECURITY;
ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinic_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- 7.1 Branches RLS
DROP POLICY IF EXISTS "Branches are readable by all authenticated users" ON branches;
CREATE POLICY "Branches are readable by all authenticated users" ON branches FOR SELECT TO authenticated USING (true);

-- 7.2 Doctors RLS
DROP POLICY IF EXISTS "Doctors are readable by all authenticated users" ON doctors;
CREATE POLICY "Doctors are readable by all authenticated users" ON doctors FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "Managers can update doctor settings" ON doctors;
CREATE POLICY "Managers can update doctor settings" ON doctors FOR ALL TO authenticated USING (get_current_user_role() = 'manager');

-- 7.3 Profiles RLS
DROP POLICY IF EXISTS "Users can read own profile" ON profiles;
CREATE POLICY "Users can read own profile" ON profiles FOR SELECT TO authenticated
    USING (auth_user_id = auth.uid() OR is_staff());
DROP POLICY IF EXISTS "Users can update own profile" ON profiles;
CREATE POLICY "Users can update own profile" ON profiles FOR UPDATE TO authenticated
    USING (auth_user_id = auth.uid());
DROP POLICY IF EXISTS "Managers can manage all profiles" ON profiles;
CREATE POLICY "Managers can manage all profiles" ON profiles FOR ALL TO authenticated
    USING (get_current_user_role() = 'manager');

-- 7.4 Patients RLS
DROP POLICY IF EXISTS "Patients can read own or family records" ON patients;
CREATE POLICY "Patients can read own or family records" ON patients FOR SELECT TO authenticated
    USING (account_id = get_current_profile_id() OR is_staff());
DROP POLICY IF EXISTS "Patients can insert/update family members" ON patients;
CREATE POLICY "Patients can insert/update family members" ON patients FOR ALL TO authenticated
    USING (account_id = get_current_profile_id() OR is_staff());

-- 7.5 Appointments RLS
DROP POLICY IF EXISTS "Patients read own appointments" ON appointments;
CREATE POLICY "Patients read own appointments" ON appointments FOR SELECT TO authenticated
    USING (
        patient_id IN (SELECT id FROM patients WHERE account_id = get_current_profile_id())
        OR is_staff()
    );
DROP POLICY IF EXISTS "Patients insert own appointments" ON appointments;
CREATE POLICY "Patients insert own appointments" ON appointments FOR INSERT TO authenticated
    WITH CHECK (
        patient_id IN (SELECT id FROM patients WHERE account_id = get_current_profile_id())
        OR is_staff()
    );
DROP POLICY IF EXISTS "Staff manage appointments" ON appointments;
CREATE POLICY "Staff manage appointments" ON appointments FOR ALL TO authenticated
    USING (is_staff());

-- 7.6 Vitals RLS
DROP POLICY IF EXISTS "Read vitals" ON appointment_vitals;
CREATE POLICY "Read vitals" ON appointment_vitals FOR SELECT TO authenticated
    USING (
        patient_id IN (SELECT id FROM patients WHERE account_id = get_current_profile_id())
        OR is_staff()
    );
DROP POLICY IF EXISTS "Staff insert/update vitals" ON appointment_vitals;
CREATE POLICY "Staff insert/update vitals" ON appointment_vitals FOR ALL TO authenticated
    USING (get_current_user_role() IN ('reception', 'doctor', 'manager'));

-- 7.7 Visits RLS
DROP POLICY IF EXISTS "Read visits" ON visits;
CREATE POLICY "Read visits" ON visits FOR SELECT TO authenticated
    USING (
        patient_id IN (SELECT id FROM patients WHERE account_id = get_current_profile_id())
        OR is_staff()
    );
DROP POLICY IF EXISTS "Doctors record visits" ON visits;
CREATE POLICY "Doctors record visits" ON visits FOR ALL TO authenticated
    USING (get_current_user_role() IN ('doctor', 'manager'));

-- 7.8 Services RLS
DROP POLICY IF EXISTS "Read services" ON services;
CREATE POLICY "Read services" ON services FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "Managers manage services" ON services;
CREATE POLICY "Managers manage services" ON services FOR ALL TO authenticated
    USING (get_current_user_role() = 'manager');

-- 7.9 Invoices & Items RLS
DROP POLICY IF EXISTS "Read invoices" ON invoice_items;
CREATE POLICY "Read invoices" ON invoice_items FOR SELECT TO authenticated
    USING (
        appointment_id IN (
            SELECT a.id FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            WHERE p.account_id = get_current_profile_id()
        )
        OR is_staff()
    );
DROP POLICY IF EXISTS "Staff manage invoice items" ON invoice_items;
CREATE POLICY "Staff manage invoice items" ON invoice_items FOR ALL TO authenticated USING (is_staff());

-- 7.10 Payments RLS
DROP POLICY IF EXISTS "Read payments" ON payments;
CREATE POLICY "Read payments" ON payments FOR SELECT TO authenticated
    USING (
        appointment_id IN (
            SELECT a.id FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            WHERE p.account_id = get_current_profile_id()
        )
        OR is_staff()
    );
DROP POLICY IF EXISTS "Staff manage payments" ON payments;
CREATE POLICY "Staff manage payments" ON payments FOR ALL TO authenticated USING (is_staff());

-- 7.11 Lab Orders RLS
DROP POLICY IF EXISTS "Lab orders access" ON lab_orders;
CREATE POLICY "Lab orders access" ON lab_orders FOR SELECT TO authenticated
    USING (
        (patient_id IN (SELECT id FROM patients WHERE account_id = get_current_profile_id()) AND status = 'confirmed')
        OR is_staff()
    );
DROP POLICY IF EXISTS "Lab technicians enter and confirm results" ON lab_orders;
CREATE POLICY "Lab technicians enter and confirm results" ON lab_orders FOR ALL TO authenticated
    USING (get_current_user_role() IN ('lab', 'manager'));

-- 7.12 Pharmacy & Stock RLS
DROP POLICY IF EXISTS "Stock items readable by staff" ON stock_items;
CREATE POLICY "Stock items readable by staff" ON stock_items FOR SELECT TO authenticated USING (is_staff());
DROP POLICY IF EXISTS "Pharmacy manages stock" ON stock_items;
CREATE POLICY "Pharmacy manages stock" ON stock_items FOR ALL TO authenticated
    USING (get_current_user_role() IN ('pharmacy', 'manager'));

DROP POLICY IF EXISTS "Stock moves readable by staff" ON stock_moves;
CREATE POLICY "Stock moves readable by staff" ON stock_moves FOR SELECT TO authenticated
    USING (get_current_user_role() IN ('pharmacy', 'manager'));
DROP POLICY IF EXISTS "Pharmacy records stock moves" ON stock_moves;
CREATE POLICY "Pharmacy records stock moves" ON stock_moves FOR INSERT TO authenticated
    WITH CHECK (get_current_user_role() IN ('pharmacy', 'manager'));

DROP POLICY IF EXISTS "Pharmacy sales view" ON pharmacy_sales;
CREATE POLICY "Pharmacy sales view" ON pharmacy_sales FOR SELECT TO authenticated
    USING (get_current_user_role() IN ('pharmacy', 'accountant', 'manager'));
DROP POLICY IF EXISTS "Pharmacy records sales" ON pharmacy_sales;
CREATE POLICY "Pharmacy records sales" ON pharmacy_sales FOR INSERT TO authenticated
    WITH CHECK (get_current_user_role() IN ('pharmacy', 'manager'));

-- 7.13 Cash Closings RLS
DROP POLICY IF EXISTS "Cash closings policy" ON cash_closings;
CREATE POLICY "Cash closings policy" ON cash_closings FOR SELECT TO authenticated
    USING (
        (get_current_user_role() = 'reception' AND by = (SELECT name FROM profiles WHERE auth_user_id = auth.uid()))
        OR get_current_user_role() IN ('accountant', 'manager')
    );
DROP POLICY IF EXISTS "Reception inserts cash closings" ON cash_closings;
CREATE POLICY "Reception inserts cash closings" ON cash_closings FOR INSERT TO authenticated
    WITH CHECK (get_current_user_role() IN ('reception', 'manager'));

-- 7.14 Expenses RLS
DROP POLICY IF EXISTS "Expenses read policy" ON expenses;
CREATE POLICY "Expenses read policy" ON expenses FOR SELECT TO authenticated
    USING (get_current_user_role() IN ('accountant', 'manager'));
DROP POLICY IF EXISTS "Accountant manages expenses" ON expenses;
CREATE POLICY "Accountant manages expenses" ON expenses FOR ALL TO authenticated
    USING (get_current_user_role() IN ('accountant', 'manager'));

-- 7.15 Clinic Settings RLS
DROP POLICY IF EXISTS "Settings readable by authenticated" ON clinic_settings;
CREATE POLICY "Settings readable by authenticated" ON clinic_settings FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "Manager updates settings" ON clinic_settings;
CREATE POLICY "Manager updates settings" ON clinic_settings FOR ALL TO authenticated
    USING (get_current_user_role() = 'manager');

-- 7.16 Audit Logs RLS
DROP POLICY IF EXISTS "Audit logs manager view" ON audit_logs;
CREATE POLICY "Audit logs manager view" ON audit_logs FOR SELECT TO authenticated
    USING (get_current_user_role() = 'manager');
DROP POLICY IF EXISTS "Audit logs insert by staff" ON audit_logs;
CREATE POLICY "Audit logs insert by staff" ON audit_logs FOR INSERT TO authenticated WITH CHECK (true);

-- 7.17 Notifications RLS
DROP POLICY IF EXISTS "Users read own notifications" ON notifications;
CREATE POLICY "Users read own notifications" ON notifications FOR SELECT TO authenticated
    USING (user_id = get_current_profile_id());
DROP POLICY IF EXISTS "Users update own notifications" ON notifications;
CREATE POLICY "Users update own notifications" ON notifications FOR UPDATE TO authenticated
    USING (user_id = get_current_profile_id());

-- =============================================================================
-- SECTION 8: AUTOMATIC PROFILE & PATIENT CREATION ON SUPABASE AUTH SIGNUP
-- =============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_supabase_user()
RETURNS TRIGGER AS $$
DECLARE
    new_profile_id BIGINT;
    user_name TEXT;
    user_phone TEXT;
BEGIN
    user_name := COALESCE(NEW.raw_user_meta_data->>'name', 'Patient ' || SUBSTRING(NEW.id::text, 1, 6));
    user_phone := COALESCE(NEW.phone, NEW.raw_user_meta_data->>'phone', '07000000000');

    -- Insert profile ensuring public signups are assigned role = 'patient'
    INSERT INTO public.profiles (auth_user_id, name, phone, role)
    VALUES (NEW.id, user_name, user_phone, 'patient')
    RETURNING id INTO new_profile_id;

    -- Automatically attach self patient record
    INSERT INTO public.patients (name, phone, account_id, relation)
    VALUES (user_name, user_phone, new_profile_id, 'self');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop if exists before re-creating
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_supabase_user();

-- =============================================================================
-- SECTION 9: SUPABASE STORAGE CONFIGURATION & POLICIES
-- =============================================================================
-- Setup private storage bucket for lab results
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'lab-results',
    'lab-results',
    false,
    2097152, -- 2MB file limit matching frontend validation
    ARRAY['application/pdf', 'image/png', 'image/jpeg']
)
ON CONFLICT (id) DO UPDATE SET
    public = false,
    file_size_limit = 2097152,
    allowed_mime_types = ARRAY['application/pdf', 'image/png', 'image/jpeg'];

-- Storage access policies
DO $$
BEGIN
    DROP POLICY IF EXISTS "Lab technicians and managers can upload lab results" ON storage.objects;
    DROP POLICY IF EXISTS "Authorized clinical users and patients can view lab files" ON storage.objects;

    CREATE POLICY "Lab technicians and managers can upload lab results" ON storage.objects FOR INSERT TO authenticated
        WITH CHECK (
            bucket_id = 'lab-results'
            AND (get_current_user_role() IN ('lab', 'manager', 'doctor'))
        );

    CREATE POLICY "Authorized clinical users and patients can view lab files" ON storage.objects FOR SELECT TO authenticated
        USING (
            bucket_id = 'lab-results'
            AND (
                is_staff()
                OR EXISTS (
                    SELECT 1 FROM lab_orders lo
                    JOIN patients p ON lo.patient_id = p.id
                    WHERE p.account_id = get_current_profile_id()
                    AND lo.status = 'confirmed'
                    AND lo.result->>'file_name' = storage.objects.name
                )
            )
        );
END $$;

-- =============================================================================
-- SECTION 10: INITIAL REFERENCE & SAFE SEED DATA
-- =============================================================================

-- 10.1 Default Clinic Settings
INSERT INTO clinic_settings (id, cancel_hours, no_show_limit, deposit_amount, prescription_days, usd_rate)
VALUES (1, 3, 3, 10000, 7, 1310)
ON CONFLICT (id) DO NOTHING;

-- 10.2 Branches
INSERT INTO branches (id, name, name_ar, address)
VALUES
    ('main', 'Al-Jadreyah Main Branch', 'الفرع الرئيسي - الجادرية', 'بغداد - الجادرية - قرب الجامعة'),
    ('second', 'Al-Mansour Branch', 'فرع المنصور', 'بغداد - المنصور - شارع 14 رمضان')
ON CONFLICT (id) DO NOTHING;

-- 10.3 Default Doctors
INSERT INTO doctors (id, name, name_ar, specialty, specialty_ar, fee, new_minutes, followup_minutes, clinic_percent, service_percent, days, absences, late_date, late_minutes)
VALUES
    (
        1,
        'Dr. Ali Hassan',
        'د. علي حسن',
        'Internal Medicine',
        'باطنية',
        25000,
        20,
        10,
        30,
        20,
        '[
            {"branch": "main", "shift": "morning"},
            {"branch": "main", "shift": "morning"},
            {"branch": "main", "shift": "morning"},
            {"branch": "main", "shift": "morning"},
            {"branch": "second", "shift": "evening"},
            null,
            {"branch": "main", "shift": "morning"}
        ]'::jsonb,
        '[]'::jsonb,
        null,
        0
    ),
    (
        2,
        'Dr. Noor Jasim',
        'د. نور جاسم',
        'Pediatrics',
        'أطفال',
        20000,
        15,
        10,
        25,
        25,
        '[
            {"branch": "second", "shift": "evening"},
            {"branch": "main", "shift": "morning"},
            {"branch": "second", "shift": "evening"},
            {"branch": "second", "shift": "evening"},
            {"branch": "second", "shift": "evening"},
            null,
            {"branch": "second", "shift": "evening"}
        ]'::jsonb,
        '[]'::jsonb,
        null,
        0
    )
ON CONFLICT (id) DO NOTHING;

-- 10.4 Clinical Services
INSERT INTO services (id, name, name_ar, kind, price, currency, template)
VALUES
    (
        1,
        'Blood sugar',
        'سكر الدم',
        'test',
        5000,
        'IQD',
        '[{"name": "Fasting glucose", "unit": "mg/dL", "ref_low": 70, "ref_high": 110}]'::jsonb
    ),
    (
        2,
        'Complete blood count',
        'تحليل دم شامل',
        'test',
        15000,
        'IQD',
        '[
            {"name": "Hemoglobin (Hb)", "unit": "g/dL", "ref_low": 12, "ref_high": 17},
            {"name": "White cells (WBC)", "unit": "10³/µL", "ref_low": 4, "ref_high": 11},
            {"name": "Red cells (RBC)", "unit": "10⁶/µL", "ref_low": 4.2, "ref_high": 5.9},
            {"name": "Platelets (PLT)", "unit": "10³/µL", "ref_low": 150, "ref_high": 450}
        ]'::jsonb
    ),
    (
        3,
        'Vitamin D',
        'فيتامين د',
        'test',
        25000,
        'IQD',
        '[{"name": "25-OH Vitamin D", "unit": "ng/mL", "ref_low": 30, "ref_high": 100}]'::jsonb
    ),
    (
        4,
        'Chest X-ray',
        'أشعة صدر',
        'xray',
        20,
        'USD',
        NULL
    ),
    (
        5,
        'Wound dressing',
        'تضميد جرح',
        'procedure',
        10000,
        'IQD',
        NULL
    )
ON CONFLICT (id) DO NOTHING;

-- 10.5 Pharmacy Stock Initial Inventory
INSERT INTO stock_items (id, name, unit, price, quantity, low_level, expires_on, barcode)
VALUES
    (60, 'Paracetamol 500mg', 'tablet', 250, 240, 50, CURRENT_DATE + INTERVAL '200 days', '06290000000011'),
    (61, 'Amoxicillin 500mg', 'capsule', 500, 30, 40, CURRENT_DATE + INTERVAL '120 days', '06290000000028'),
    (62, 'Vitamin D3 5000 IU', 'capsule', 750, 0, 20, CURRENT_DATE + INTERVAL '300 days', NULL),
    (63, 'Omeprazole 20mg', 'capsule', 400, 120, 30, CURRENT_DATE + INTERVAL '18 days', '06290000000035'),
    (64, 'Amlodipine 5mg', 'tablet', 300, 90, 30, CURRENT_DATE + INTERVAL '400 days', NULL),
    (65, 'Cetirizine 10mg', 'tablet', 250, 60, 20, CURRENT_DATE + INTERVAL '150 days', NULL),
    (66, 'Ibuprofen 400mg', 'tablet', 250, 45, 20, CURRENT_DATE - INTERVAL '3 days', NULL),
    (67, 'Cough syrup 100ml', 'bottle', 3000, 12, 5, NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- 10.6 Default Staff & Patient Profiles (Password: password123, argon2/bcrypt hash provided)
-- Hash generated for 'password123': $2b$12$D23r510619S.cT7i1a243O1nZ6pG4yJ95U7iZ8cM7A.u7H7UuWJ1C
INSERT INTO profiles (id, name, phone, password_hash, role, doctor_id)
VALUES
    (1, 'سارة موظفة', '07800000001', '$2b$12$K1r6fQ/w82sF9WbM4Rz6UuxP0P8wL4QzGqJb1Xm6uL1H.Z3y4qj1K', 'reception', NULL),
    (2, 'د. علي حسن', '07800000002', '$2b$12$K1r6fQ/w82sF9WbM4Rz6UuxP0P8wL4QzGqJb1Xm6uL1H.Z3y4qj1K', 'doctor', 1),
    (3, 'د. نور جاسم', '07800000003', '$2b$12$K1r6fQ/w82sF9WbM4Rz6UuxP0P8wL4QzGqJb1Xm6uL1H.Z3y4qj1K', 'doctor', 2),
    (4, 'أحمد الصيدلي', '07800000004', '$2b$12$K1r6fQ/w82sF9WbM4Rz6UuxP0P8wL4QzGqJb1Xm6uL1H.Z3y4qj1K', 'pharmacy', NULL),
    (5, 'زينب كريم', '07800000005', '$2b$12$K1r6fQ/w82sF9WbM4Rz6UuxP0P8wL4QzGqJb1Xm6uL1H.Z3y4qj1K', 'patient', NULL),
    (6, 'مدير المجمع', '07800000006', '$2b$12$K1r6fQ/w82sF9WbM4Rz6UuxP0P8wL4QzGqJb1Xm6uL1H.Z3y4qj1K', 'manager', NULL),
    (7, 'حيدر المختبر', '07800000007', '$2b$12$K1r6fQ/w82sF9WbM4Rz6UuxP0P8wL4QzGqJb1Xm6uL1H.Z3y4qj1K', 'lab', NULL),
    (8, 'رنا المحاسبة', '07800000008', '$2b$12$K1r6fQ/w82sF9WbM4Rz6UuxP0P8wL4QzGqJb1Xm6uL1H.Z3y4qj1K', 'accountant', NULL),
    (9, 'موظف الاستقبال', '07701234567', 'pbkdf2:sha256:100000$0533f23a6b1b6b3439af881d8df3067d$8f0b0bada71a87ab15ddf6cf986f79a50c81775b098c84d9a1e13184c66d2741', 'reception', NULL),
    (10, 'د. علي حسن', '07702345678', 'pbkdf2:sha256:100000$920710ec27e4aead7f25b8a5986f6145$154116bf3dfc800c6fd34abf8d058de6fc82fb181a8bbe88c7d6b2971b77b1e0', 'doctor', 1),
    (11, 'صيدلاني المركز', '07703456789', 'pbkdf2:sha256:100000$ac59417ed38fcd5c8590b2bc7bd61e9e$a21792e0c5dee40881d90e6e7eaf11825d1410f8f95ee26db5a15ee6ae25aa68', 'pharmacy', NULL),
    (12, 'فني المختبر', '07704567890', 'pbkdf2:sha256:100000$f91f916c91bf93558b61e020d8e3cafa$48fe341aee1c161d92065a26e38eca2cb87c0d776f8f11eee6ed5baefae9744c', 'lab', NULL),
    (13, 'المحاسب المالي', '07705678901', 'pbkdf2:sha256:100000$9fb6658074f8de2a1ec93daaa32ada30$e14389e259573f6a78169c14868813249fd8cb5bce2f70112d9b9492f8470a59', 'accountant', NULL),
    (14, 'مدير المركز', '07706789012', 'pbkdf2:sha256:100000$42bf84ddaa0e78772ff108e618c7ced5$b8cb7a5ec7e591522cb4204be3b15144dfe2025ca5375187db934b123cb51f8d', 'manager', NULL),
    (15, 'المريض التجريبي', '07707890123', 'pbkdf2:sha256:100000$0aa3982d8deb50202714b58b54b2048b$8a32b0ec663a2286e56ac5b7bc88c6d44000131bb1fc7f7e80018f43daa86369', 'patient', NULL)
ON CONFLICT (id) DO NOTHING;

-- 10.7 Seed Patients
INSERT INTO patients (id, name, phone, account_id, relation, allergies, conditions, blood_type)
VALUES
    (1, 'زينب كريم', '07800000005', 5, 'self', '[]'::jsonb, '[]'::jsonb, NULL),
    (2, 'مصطفى كريم', '07700000002', 5, 'child', '[]'::jsonb, '[]'::jsonb, NULL),
    (3, 'حسن عباس', '07700000003', NULL, 'self', '[]'::jsonb, '[]'::jsonb, NULL),
    (4, 'مريم ناصر', '07700000004', NULL, 'self', '["Aspirin", "Ibuprofen"]'::jsonb, '["ارتفاع ضغط الدم"]'::jsonb, 'O+'),
    (5, 'المريض التجريبي', '07707890123', 15, 'self', '[]'::jsonb, '[]'::jsonb, NULL)
ON CONFLICT (id) DO NOTHING;

-- Reset primary key sequences to ensure future auto-increments start beyond initial seed IDs
SELECT setval('doctors_id_seq', (SELECT GREATEST(MAX(id), 10) FROM doctors));
SELECT setval('profiles_id_seq', (SELECT GREATEST(MAX(id), 100) FROM profiles));
SELECT setval('patients_id_seq', (SELECT GREATEST(MAX(id), 100) FROM patients));
SELECT setval('services_id_seq', (SELECT GREATEST(MAX(id), 20) FROM services));
SELECT setval('stock_items_id_seq', (SELECT GREATEST(MAX(id), 100) FROM stock_items));
SELECT setval('appointments_id_seq', (SELECT GREATEST(COALESCE(MAX(id), 0), 100) FROM appointments));
SELECT setval('visits_id_seq', (SELECT GREATEST(COALESCE(MAX(id), 0), 100) FROM visits));
SELECT setval('invoice_items_id_seq', (SELECT GREATEST(COALESCE(MAX(id), 0), 100) FROM invoice_items));
SELECT setval('payments_id_seq', (SELECT GREATEST(COALESCE(MAX(id), 0), 100) FROM payments));
SELECT setval('lab_orders_id_seq', (SELECT GREATEST(COALESCE(MAX(id), 0), 100) FROM lab_orders));
SELECT setval('stock_moves_id_seq', (SELECT GREATEST(COALESCE(MAX(id), 0), 100) FROM stock_moves));
SELECT setval('pharmacy_sales_id_seq', (SELECT GREATEST(COALESCE(MAX(id), 0), 100) FROM pharmacy_sales));
SELECT setval('cash_closings_id_seq', (SELECT GREATEST(COALESCE(MAX(id), 0), 100) FROM cash_closings));
SELECT setval('expenses_id_seq', (SELECT GREATEST(COALESCE(MAX(id), 0), 100) FROM expenses));
SELECT setval('notifications_id_seq', (SELECT GREATEST(COALESCE(MAX(id), 0), 100) FROM notifications));
SELECT setval('audit_logs_id_seq', (SELECT GREATEST(COALESCE(MAX(id), 0), 100) FROM audit_logs));

-- =============================================================================
-- END OF SCHEMA INITIALIZATION SCRIPT
-- =============================================================================

-- 4.21 Payment Sessions (Online Payments via Qi Card)
CREATE TABLE IF NOT EXISTS payment_sessions (
    id VARCHAR(64) PRIMARY KEY,
    appointment_id BIGINT NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES profiles(id) ON DELETE SET NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'IQD',
    status VARCHAR(32) NOT NULL DEFAULT 'created',
    form_url VARCHAR(512) NOT NULL DEFAULT '',
    return_url VARCHAR(512) NOT NULL DEFAULT '',
    key VARCHAR(128) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    outcome VARCHAR(128),
    settled_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_payment_sessions_appointment ON payment_sessions(appointment_id);
CREATE INDEX IF NOT EXISTS idx_payment_sessions_user ON payment_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_sessions_key ON payment_sessions(key);

-- 4.22 Social Welfare Requests (الرعاية الاجتماعية)
CREATE TABLE IF NOT EXISTS welfare_requests (
    id BIGSERIAL PRIMARY KEY,
    patient_id BIGINT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    patient_name VARCHAR(128) NOT NULL,
    patient_phone VARCHAR(32) NOT NULL,
    card_number VARCHAR(64) NOT NULL,
    photo_url VARCHAR(512) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by VARCHAR(128),
    reviewed_at TIMESTAMPTZ,
    valid_until DATE,
    reject_reason TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_welfare_requests_patient ON welfare_requests(patient_id);
CREATE INDEX IF NOT EXISTS idx_welfare_requests_status ON welfare_requests(status);

-- 4.14 Idempotency Records
CREATE TABLE IF NOT EXISTS idempotency_records (
    key VARCHAR(128) PRIMARY KEY,
    user_id BIGINT REFERENCES profiles(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    response_status INTEGER NOT NULL,
    response_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_idempotency_records_action ON idempotency_records(action);


-- =============================================================================
-- 4.23 Real-time Connection Tickets
-- =============================================================================
CREATE TABLE IF NOT EXISTS realtime_connection_tickets (
    id BIGSERIAL PRIMARY KEY,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    user_id BIGINT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_realtime_tickets_hash ON realtime_connection_tickets(token_hash);
CREATE INDEX IF NOT EXISTS idx_realtime_tickets_user ON realtime_connection_tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_realtime_tickets_active ON realtime_connection_tickets(token_hash)
    WHERE consumed_at IS NULL AND revoked_at IS NULL;

-- =============================================================================
-- 4.24 Transactional Outbox Events
-- =============================================================================
CREATE TABLE IF NOT EXISTS outbox_events (
    id BIGSERIAL PRIMARY KEY,
    event_uuid VARCHAR(36) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    channel VARCHAR(150) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    correlation_id VARCHAR(64),
    retry_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_outbox_events_channel ON outbox_events(channel);
CREATE INDEX IF NOT EXISTS idx_outbox_events_type ON outbox_events(event_type);
CREATE INDEX IF NOT EXISTS idx_outbox_events_created ON outbox_events(created_at);

-- Trigger to notify listening workers of new outbox events via PostgreSQL LISTEN/NOTIFY
CREATE OR REPLACE FUNCTION notify_outbox_event()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('realtime_events', NEW.id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_outbox_event_notify ON outbox_events;
CREATE TRIGGER trg_outbox_event_notify
AFTER INSERT ON outbox_events
FOR EACH ROW
EXECUTE FUNCTION notify_outbox_event();

-- =============================================================================
-- 4.25 Distributed Rate Limit Entries
-- =============================================================================
CREATE TABLE IF NOT EXISTS rate_limit_entries (
    id BIGSERIAL PRIMARY KEY,
    bucket_key VARCHAR(128) UNIQUE NOT NULL,
    counter INTEGER NOT NULL DEFAULT 1,
    window_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_entries_key ON rate_limit_entries(bucket_key);
CREATE INDEX IF NOT EXISTS idx_rate_limit_entries_expires ON rate_limit_entries(expires_at);

-- =============================================================================
-- 4.26 User Sessions & Token Tracking
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    jti VARCHAR(64) UNIQUE NOT NULL,
    device_info VARCHAR(256),
    ip_address VARCHAR(64),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash ON user_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_user_sessions_jti ON user_sessions(jti);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);

-- =============================================================================
-- 4.27 Password Reset OTPs
-- =============================================================================
CREATE TABLE IF NOT EXISTS password_reset_otps (
    id BIGSERIAL PRIMARY KEY,
    phone VARCHAR(32) UNIQUE NOT NULL,
    otp_hash VARCHAR(128) NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    cooldown_until TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_password_reset_otps_phone ON password_reset_otps(phone);

-- =============================================================================
-- SECTION 7.18+ : Additional Row Level Security (RLS) Policies
-- =============================================================================
ALTER TABLE patient_merges ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE welfare_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_reset_otps ENABLE ROW LEVEL SECURITY;
ALTER TABLE realtime_connection_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_limit_entries ENABLE ROW LEVEL SECURITY;

-- patient_merges RLS
DROP POLICY IF EXISTS "Staff manage patient merges" ON patient_merges;
CREATE POLICY "Staff manage patient merges" ON patient_merges FOR ALL TO authenticated
    USING (is_staff());

-- payment_sessions RLS
DROP POLICY IF EXISTS "Users read own payment sessions" ON payment_sessions;
CREATE POLICY "Users read own payment sessions" ON payment_sessions FOR SELECT TO authenticated
    USING (
        user_id = get_current_profile_id()
        OR appointment_id IN (
            SELECT a.id FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            WHERE p.account_id = get_current_profile_id()
        )
        OR is_staff()
    );

DROP POLICY IF EXISTS "Users create own payment sessions" ON payment_sessions;
CREATE POLICY "Users create own payment sessions" ON payment_sessions FOR INSERT TO authenticated
    WITH CHECK (
        user_id = get_current_profile_id()
        OR is_staff()
    );

-- welfare_requests RLS
DROP POLICY IF EXISTS "Patients read own welfare requests" ON welfare_requests;
CREATE POLICY "Patients read own welfare requests" ON welfare_requests FOR SELECT TO authenticated
    USING (
        patient_id IN (SELECT id FROM patients WHERE account_id = get_current_profile_id())
        OR is_staff()
    );

DROP POLICY IF EXISTS "Patients submit welfare requests" ON welfare_requests;
CREATE POLICY "Patients submit welfare requests" ON welfare_requests FOR INSERT TO authenticated
    WITH CHECK (
        patient_id IN (SELECT id FROM patients WHERE account_id = get_current_profile_id())
        OR is_staff()
    );

DROP POLICY IF EXISTS "Staff manage welfare requests" ON welfare_requests;
CREATE POLICY "Staff manage welfare requests" ON welfare_requests FOR ALL TO authenticated
    USING (get_current_user_role() IN ('reception', 'manager'));

-- idempotency_records RLS
DROP POLICY IF EXISTS "Users access own idempotency" ON idempotency_records;
CREATE POLICY "Users access own idempotency" ON idempotency_records FOR ALL TO authenticated
    USING (user_id = get_current_profile_id() OR is_staff());

-- user_sessions RLS
DROP POLICY IF EXISTS "Users manage own sessions" ON user_sessions;
CREATE POLICY "Users manage own sessions" ON user_sessions FOR ALL TO authenticated
    USING (user_id = get_current_profile_id() OR get_current_user_role() = 'manager');
DROP POLICY IF EXISTS "Backend service manages user sessions" ON user_sessions;
CREATE POLICY "Backend service manages user sessions" ON user_sessions FOR ALL
    USING (true) WITH CHECK (true);
REVOKE ALL ON TABLE user_sessions FROM public, anon;

-- password_reset_otps RLS
DROP POLICY IF EXISTS "Manager only direct access to OTPs" ON password_reset_otps;
CREATE POLICY "Manager only direct access to OTPs" ON password_reset_otps FOR ALL TO authenticated
    USING (get_current_user_role() = 'manager');
DROP POLICY IF EXISTS "Backend service manages OTPs" ON password_reset_otps;
CREATE POLICY "Backend service manages OTPs" ON password_reset_otps FOR ALL
    USING (true) WITH CHECK (true);
REVOKE ALL ON TABLE password_reset_otps FROM public, anon;

-- realtime_connection_tickets RLS
DROP POLICY IF EXISTS "Users manage own tickets" ON realtime_connection_tickets;
DROP POLICY IF EXISTS "Backend service manages tickets" ON realtime_connection_tickets;
CREATE POLICY "Backend service manages tickets" ON realtime_connection_tickets FOR ALL
    USING (true) WITH CHECK (true);
REVOKE ALL ON TABLE realtime_connection_tickets FROM public, anon;

-- outbox_events RLS
DROP POLICY IF EXISTS "Staff read outbox events" ON outbox_events;
DROP POLICY IF EXISTS "Backend service manages outbox" ON outbox_events;
CREATE POLICY "Backend service manages outbox" ON outbox_events FOR ALL
    USING (true) WITH CHECK (true);
REVOKE ALL ON TABLE outbox_events FROM public, anon;

-- rate_limit_entries RLS
-- Rate limiting is an internal backend infrastructure mechanism executed on unauthenticated
-- and authenticated requests alike. Access is restricted to the backend application database role.
DROP POLICY IF EXISTS "Manager only view rate limits" ON rate_limit_entries;
DROP POLICY IF EXISTS "Backend service manages rate limits" ON rate_limit_entries;
CREATE POLICY "Backend service manages rate limits" ON rate_limit_entries FOR ALL
    USING (true) WITH CHECK (true);
REVOKE ALL ON TABLE rate_limit_entries FROM public, anon;
