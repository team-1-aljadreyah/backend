import asyncio
from datetime import datetime, timedelta
from app.database.connection import engine
from sqlalchemy import text
import pytest


@pytest.mark.asyncio
async def test_live_supabase_gist_exclusion_constraint():
    """Directly verifies PostgreSQL GiST exclusion constraint on live Supabase pooler."""
    if engine.dialect.name != "postgresql":
        pytest.skip("Test requires live PostgreSQL (Supabase) engine")
    async with engine.begin() as conn:
        # Check that the exclusion constraint exists
        res = await conn.execute(text("""
            SELECT conname, contype 
            FROM pg_constraint 
            WHERE conname = 'exclude_overlapping_doctor_appointments'
        """))
        row = res.fetchone()
        assert row is not None, "Exclusion constraint exclude_overlapping_doctor_appointments must exist"
        assert row[1] == "x" or row[1] == b"x", f"Expected 'x' for exclusion constraint, got {row[1]}"

        # Test inserting an appointment range: Doctor 1, 2030-01-01 10:00 to 10:20
        # Clean up any test records from 2030-01-01
        await conn.execute(text("DELETE FROM appointments WHERE date = '2030-01-01'"))

        # Find a valid patient
        p_res = await conn.execute(text("SELECT id FROM patients LIMIT 1"))
        patient_id = p_res.scalar()

        st1 = datetime.fromisoformat("2030-01-01T10:00:00+03:00")
        et1 = datetime.fromisoformat("2030-01-01T10:20:00+03:00")

        await conn.execute(text("""
            INSERT INTO appointments (patient_id, doctor_id, date, time, start_time, end_time, kind, branch, status)
            VALUES (:pid, 1, '2030-01-01', '10:00', :st, :et, 'new', 'main', 'booked')
        """), {"pid": patient_id, "st": st1, "et": et1})

    # In a separate transaction, attempt to insert an overlapping range: 10:10 to 10:30
    st_overlap = datetime.fromisoformat("2030-01-01T10:10:00+03:00")
    et_overlap = datetime.fromisoformat("2030-01-01T10:30:00+03:00")

    overlap_rejected = False
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                INSERT INTO appointments (patient_id, doctor_id, date, time, start_time, end_time, kind, branch, status)
                VALUES (:pid, 1, '2030-01-01', '10:10', :st, :et, 'new', 'main', 'booked')
            """), {"pid": patient_id, "st": st_overlap, "et": et_overlap})
    except Exception as e:
        overlap_rejected = True
        err_msg = str(e).lower()
        assert "exclude_overlapping_doctor_appointments" in err_msg or "exclusion" in err_msg or "conflicting key" in err_msg

    assert overlap_rejected, "PostgreSQL GiST exclusion constraint MUST reject overlapping appointment range"

    # Now test adjacent range: 10:20 to 10:40 (should succeed without conflict)
    st_adjacent = datetime.fromisoformat("2030-01-01T10:20:00+03:00")
    et_adjacent = datetime.fromisoformat("2030-01-01T10:40:00+03:00")

    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO appointments (patient_id, doctor_id, date, time, start_time, end_time, kind, branch, status)
            VALUES (:pid, 1, '2030-01-01', '10:20', :st, :et, 'new', 'main', 'booked')
        """), {"pid": patient_id, "st": st_adjacent, "et": et_adjacent})

        # Cleanup test rows
        await conn.execute(text("DELETE FROM appointments WHERE date = '2030-01-01'"))

    print("PostgreSQL GiST exclusion constraint passed all tests on live Supabase DB!")


if __name__ == "__main__":
    asyncio.run(test_live_supabase_gist_exclusion_constraint())
