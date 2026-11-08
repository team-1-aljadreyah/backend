import io
import unittest
from datetime import date, timedelta
from tests.conftest import get_test_client, auth_headers
from app.core.security import get_password_hash, verify_password, create_refresh_token, create_access_token


class TestAuditComprehensive(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        self.reception_headers = auth_headers(user_id=1, role="reception")
        self.doctor1_headers = auth_headers(user_id=2, role="doctor")
        self.doctor2_headers = auth_headers(user_id=3, role="doctor")
        self.manager_headers = auth_headers(user_id=6, role="manager")
        self.patient_headers = auth_headers(user_id=5, role="patient")
        self.other_patient_headers = auth_headers(user_id=7, role="patient")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_reception_blocked_from_clinical_routes(self):
        """SEC-CLIN-01: Reception must be blocked from alerts, vitals, and visits."""
        # Alerts
        res1 = await self.client.get("/patients/1/alerts", headers=self.reception_headers)
        self.assertEqual(res1.status_code, 403)

        # Vitals
        res2 = await self.client.get("/patients/1/vitals", headers=self.reception_headers)
        self.assertEqual(res2.status_code, 403)

        # Visits
        res3 = await self.client.get("/patients/1/visits", headers=self.reception_headers)
        self.assertEqual(res3.status_code, 403)

    async def test_mock_token_strictly_rejected(self):
        """SEC-AUTH-01: Mock tokens (mock-token-*) must be strictly rejected."""
        mock_headers = {"Authorization": "Bearer mock-token-6"}
        res = await self.client.get("/users", headers=mock_headers)
        self.assertEqual(res.status_code, 401)

    async def test_refresh_token_rejected_on_protected_api(self):
        """SEC-AUTH-02: Refresh tokens must NOT be accepted on protected API routes."""
        refresh_token = create_refresh_token({"sub": "6", "role": "manager"})
        res = await self.client.get("/users", headers={"Authorization": f"Bearer {refresh_token}"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["code"], "unauthorized")

    async def test_argon2id_password_hashing(self):
        """SEC-AUTH-03: Argon2id modern password hashing."""
        pwd = "TestSecurePassword123!"
        hashed = get_password_hash(pwd)
        self.assertTrue(hashed.startswith("$argon2id$"))
        self.assertTrue(verify_password(pwd, hashed))
        self.assertFalse(verify_password("WrongPassword123!", hashed))

    async def test_file_upload_magic_bytes_and_path_traversal(self):
        """SEC-FILE-01: Uploads must verify magic bytes and sanitize filenames."""
        # 1. Corrupted file claiming to be PNG
        fake_png = io.BytesIO(b"NOT_A_REAL_PNG_HEADER_TEST")
        files = {"photo": ("malicious.png", fake_png, "image/png")}
        res = await self.client.post(
            "/patients/1/welfare",
            data={"card_number": "WELFARE-TRAVERSAL"},
            files=files,
            headers=self.patient_headers,
        )
        self.assertEqual(res.status_code, 422)

        # 2. Path traversal in filename
        fake_png_valid = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        files = {"photo": ("../../traversal.png", fake_png_valid, "image/png")}
        res2 = await self.client.post(
            "/patients/1/welfare",
            data={"card_number": "WELFARE-TRAVERSAL"},
            files=files,
            headers=self.patient_headers,
        )
        self.assertEqual(res2.status_code, 422)

    async def test_appointment_state_machine_checkin(self):
        """SEC-APPT-01: Cannot check in an appointment that is not booked."""
        # Non-existent or cancelled appointment checkin
        res = await self.client.post(
            "/appointments/999999/check-in",
            json={"emergency": False},
            headers=self.reception_headers,
        )
        self.assertEqual(res.status_code, 404)

    async def test_realtime_ticket_generation(self):
        """SEC-REALTIME: Single-use ticket generation for WebSockets."""
        res = await self.client.post("/realtime/ticket", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertIn("ticket", data)
        self.assertEqual(data["expires_in"], 60)

    async def test_idempotency_cross_user_conflict(self):
        """SEC-IDEMP-01: Idempotency keys must be scoped and reject cross-user collisions."""
        from app.core.idempotency import save_idempotency_record, check_idempotency
        from app.core.exceptions import ConflictException
        from app.database.connection import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            # User 1 saves record
            await save_idempotency_record(
                session, "unique_tx_key_101", "payment.test", {"amount": 100}, 200, {"success": True}, user_id=1
            )
            await session.commit()

            # Same user with same payload: returns cached
            cached = await check_idempotency(session, "unique_tx_key_101", "payment.test", {"amount": 100}, user_id=1)
            self.assertIsNotNone(cached)
            self.assertEqual(cached[0], 200)

            # Different user with same key: raises ConflictException
            with self.assertRaises(ConflictException):
                await check_idempotency(session, "unique_tx_key_101", "payment.test", {"amount": 100}, user_id=2)

            # Same user with different payload: raises ConflictException
            with self.assertRaises(ConflictException):
                await check_idempotency(session, "unique_tx_key_101", "payment.test", {"amount": 200}, user_id=1)
