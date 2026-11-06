import asyncio
from app.database.connection import engine
from sqlalchemy import text
from app.core.security import normalize_phone_local
import re
from datetime import datetime, timedelta, timezone

def normalize_patient_name(name: str) -> str:
    if not name:
        return ""
    s = name.strip()
    # Remove diacritics / tashkeel and tatweel
    s = re.sub(r"[\u064B-\u0652\u0640]", "", s)
    # Normalize Alefs
    s = re.sub(r"[أإآٱ]", "ا", s)
    # Normalize Taa Marbuta
    s = re.sub(r"ة", "ه", s)
    # Normalize Alef Maksura / Yaa
    s = re.sub(r"[ىي]", "ي", s)
    s = re.sub(r"ؤ", "و", s)
    s = re.sub(r"ئ", "ي", s)
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

statements = [
    "CREATE EXTENSION IF NOT EXISTS btree_gist;",
    "ALTER TABLE patients ADD COLUMN IF NOT EXISTS normalized_name VARCHAR(128);",
    "ALTER TABLE patients ADD COLUMN IF NOT EXISTS normalized_phone VARCHAR(32);",
    "ALTER TABLE patients ADD COLUMN IF NOT EXISTS merged_into_patient_id BIGINT REFERENCES patients(id) ON DELETE SET NULL;",
    "ALTER TABLE patients ADD COLUMN IF NOT EXISTS merged_at TIMESTAMPTZ;",
    "ALTER TABLE patients ADD COLUMN IF NOT EXISTS merged_by VARCHAR(128);",
    "ALTER TABLE patients ADD COLUMN IF NOT EXISTS merge_reason TEXT;",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS start_time TIMESTAMPTZ;",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ;",
    """CREATE TABLE IF NOT EXISTS patient_merges (
        id BIGSERIAL PRIMARY KEY,
        source_patient_id BIGINT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        target_patient_id BIGINT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        merged_by_id BIGINT NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
        merged_by_name VARCHAR(128) NOT NULL,
        merge_reason TEXT NOT NULL,
        records_transferred JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );""",
    "CREATE INDEX IF NOT EXISTS idx_patient_merges_source ON patient_merges(source_patient_id);",
    "CREATE INDEX IF NOT EXISTS idx_patient_merges_target ON patient_merges(target_patient_id);",
    """CREATE TABLE IF NOT EXISTS idempotency_records (
        key VARCHAR(128) PRIMARY KEY,
        user_id BIGINT REFERENCES profiles(id) ON DELETE SET NULL,
        action VARCHAR(64) NOT NULL,
        request_hash VARCHAR(64) NOT NULL,
        response_status INTEGER NOT NULL,
        response_data JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );""",
    "CREATE INDEX IF NOT EXISTS idx_idempotency_records_action ON idempotency_records(action);",
]

async def run_migration():
    print("Executing DDL statements...")
    async with engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))

    print("Backfilling normalized fields in patients...")
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT id, name, phone FROM patients"))
        rows = res.fetchall()
        for pid, name, phone in rows:
            norm_name = normalize_patient_name(name)
            norm_phone = normalize_phone_local(phone)
            await conn.execute(
                text("UPDATE patients SET normalized_name = :nn, normalized_phone = :np WHERE id = :pid"),
                {"nn": norm_name, "np": norm_phone, "pid": pid}
            )

    print("Creating partial unique index on patients (normalized_phone, normalized_name)...")
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_patient_phone_name
            ON patients (normalized_phone, normalized_name)
            WHERE merged_into_patient_id IS NULL;
        """))

    print("Backfilling start_time and end_time for existing appointments...")
    async with engine.begin() as conn:
        # Load doctor durations
        d_res = await conn.execute(text("SELECT id, new_minutes, followup_minutes FROM doctors"))
        doc_durations = {row[0]: {"new": row[1], "followup": row[2]} for row in d_res.fetchall()}

        a_res = await conn.execute(text("SELECT id, doctor_id, date, time, kind FROM appointments WHERE time <> '' AND time IS NOT NULL"))
        appts = a_res.fetchall()
        for aid, doc_id, adate, atime, akind in appts:
            duration = doc_durations.get(doc_id, {}).get(akind, 20)
            try:
                # Asia/Baghdad is UTC+3
                start_dt = datetime.fromisoformat(f"{adate}T{atime}:00+03:00")
                end_dt = start_dt + timedelta(minutes=duration)
                await conn.execute(
                    text("UPDATE appointments SET start_time = :st, end_time = :et WHERE id = :aid"),
                    {"st": start_dt, "et": end_dt, "aid": aid}
                )
            except Exception as e:
                print(f"Skipping appt {aid}: {e}")

    print("Adding PostgreSQL GiST exclusion constraint on appointments...")
    async with engine.begin() as conn:
        await conn.execute(text("""
            DO $$
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
            END $$;
        """))

    print("Migration finished successfully!")

if __name__ == "__main__":
    asyncio.run(run_migration())
