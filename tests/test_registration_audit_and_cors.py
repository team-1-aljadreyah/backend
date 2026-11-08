import asyncio
import unittest
from unittest.mock import patch
from sqlalchemy import select, delete
from sqlalchemy.exc import ProgrammingError, OperationalError
from tests.conftest import get_test_client
from app.database.connection import AsyncSessionLocal
from app.database.models.profile import Profile
from app.database.models.patient import Patient
from app.database.models.realtime import RateLimitEntry
from app.core.rate_limiter import check_rate_limit


class TestRegistrationAuditAndCORS(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        async with AsyncSessionLocal() as session:
            await session.execute(delete(RateLimitEntry))
            await session.commit()

    async def asyncTearDown(self):
        await self.client.aclose()

    # 1. Successful registration
    async def test_01_successful_registration(self):
        payload = {
            "name": "حيدر علي حسن",
            "phone": "07711223344",
            "password": "Password123!",
        }
        res = await self.client.post("/auth/register", json=payload, headers={"Origin": "https://alrahma.ama8.uk"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertIn("access_token", body["data"])
        self.assertIn("refresh_token", body["data"])
        self.assertEqual(body["data"]["user"]["role"], "patient")
        self.assertEqual(body["data"]["user"]["phone"], "07711223344")
        self.assertEqual(body["data"]["user"]["name"], "حيدر علي حسن")

    # 2. Duplicate profile phone
    async def test_02_duplicate_profile_phone(self):
        # Register first
        phone = "07711998877"
        payload = {
            "name": "عمار ياسر عبدالكريم",
            "phone": phone,
            "password": "Password123!",
        }
        res1 = await self.client.post("/auth/register", json=payload)
        self.assertEqual(res1.status_code, 200)

        # Attempt to register again with same phone
        payload2 = {
            "name": "زيد ياسر عبدالكريم",
            "phone": phone,
            "password": "Password456!",
        }
        res2 = await self.client.post("/auth/register", json=payload2, headers={"Origin": "https://alrahma.ama8.uk"})
        self.assertEqual(res2.status_code, 409)
        body = res2.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], "phone_taken")
        self.assertEqual(body["message"], "Phone number is already registered")

    # 3. Duplicate unlinked walk-in patient
    async def test_03_duplicate_unlinked_walk_in_patient(self):
        walk_in_phone = "07733445566"
        walk_in_name = "كرار حيدر ناصر"

        # Create an unlinked walk-in patient in database
        async with AsyncSessionLocal() as session:
            from app.core.security import normalize_phone_local, normalize_patient_name
            walk_in = Patient(
                name=walk_in_name,
                phone=walk_in_phone,
                normalized_name=normalize_patient_name(walk_in_name),
                normalized_phone=normalize_phone_local(walk_in_phone),
                account_id=None,
                relation="self",
                allergies=[],
                conditions=[],
            )
            session.add(walk_in)
            await session.commit()
            walk_in_id = walk_in.id

        # Patient attempts to self-register with matching name and phone
        reg_payload = {
            "name": walk_in_name,
            "phone": walk_in_phone,
            "password": "SecurePassword123!",
        }
        res = await self.client.post("/auth/register", json=reg_payload, headers={"Origin": "https://alrahma.ama8.uk"})
        self.assertEqual(res.status_code, 409)
        body = res.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], "patient_record_exists")
        self.assertIn("already exists", body["message"])

        # Verify walk-in record was NOT automatically claimed, deleted, or modified
        async with AsyncSessionLocal() as session:
            stmt = select(Patient).where(Patient.id == walk_in_id)
            p = (await session.execute(stmt)).scalar_one_or_none()
            self.assertIsNotNone(p)
            self.assertIsNone(p.account_id)
            self.assertEqual(p.name, walk_in_name)

    # 4. Invalid three-part name
    async def test_04_invalid_three_part_name(self):
        # 2 parts
        res2 = await self.client.post("/auth/register", json={
            "name": "علي حسن",
            "phone": "07744556677",
            "password": "Password123!",
        })
        self.assertEqual(res2.status_code, 422)
        self.assertEqual(res2.json()["code"], "invalid_name")

        # 4 parts
        res4 = await self.client.post("/auth/register", json={
            "name": "علي حسن حسين كاظم",
            "phone": "07744556678",
            "password": "Password123!",
        })
        self.assertEqual(res4.status_code, 422)
        self.assertEqual(res4.json()["code"], "invalid_name")

        # 1 part
        res1 = await self.client.post("/auth/register", json={
            "name": "علي",
            "phone": "07744556679",
            "password": "Password123!",
        })
        self.assertEqual(res1.status_code, 422)
        self.assertEqual(res1.json()["code"], "invalid_name")

    # 5. Database rate limiter table missing
    async def test_05_database_rate_limiter_table_missing(self):
        # Simulate rate limiter table missing by raising ProgrammingError inside check_rate_limit
        with patch("app.core.rate_limiter.select", side_effect=ProgrammingError("SELECT", {}, Exception('relation "rate_limit_entries" does not exist'))):
            reg_payload = {
                "name": "سامر نوري كامل",
                "phone": "07755667788",
                "password": "Password123!",
            }
            res = await self.client.post("/auth/register", json=reg_payload)
            # Must NOT crash with 500! Must fail open gracefully.
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.json()["success"])

    # 6. Rate limiter permission failure
    async def test_06_rate_limiter_permission_failure(self):
        # Simulate RLS permission denied
        with patch("app.core.rate_limiter.select", side_effect=OperationalError("SELECT", {}, Exception('permission denied for table rate_limit_entries'))):
            reg_payload = {
                "name": "مازن جاسم كريم",
                "phone": "07766778899",
                "password": "Password123!",
            }
            res = await self.client.post("/auth/register", json=reg_payload)
            # Must NOT crash with 500!
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.json()["success"])

    # 7. Rate limiter concurrent requests
    async def test_07_rate_limiter_concurrent_requests(self):
        # Check that check_rate_limit properly counts and triggers 429 when max_requests exceeded
        async with AsyncSessionLocal() as session:
            ip = "192.168.1.100"
            # Limit is 5
            for i in range(5):
                allowed, remaining, retry_after = await check_rate_limit(
                    db=session,
                    key_prefix="test_concurrent",
                    raw_identifier=ip,
                    max_requests=5,
                    window_seconds=60,
                )
                self.assertTrue(allowed)
            await session.commit()

            # 6th request should be blocked
            allowed, remaining, retry_after = await check_rate_limit(
                db=session,
                key_prefix="test_concurrent",
                raw_identifier=ip,
                max_requests=5,
                window_seconds=60,
            )
            self.assertFalse(allowed)
            self.assertEqual(remaining, 0)
            self.assertGreaterEqual(retry_after, 1)

    # 8. Database rollback after registration failure
    async def test_08_database_rollback_after_registration_failure(self):
        target_phone = "07777889900"
        target_name = "ياسين كاظم جواد"

        # Plant walk-in conflict
        async with AsyncSessionLocal() as session:
            from app.core.security import normalize_phone_local, normalize_patient_name
            walk_in = Patient(
                name=target_name,
                phone=target_phone,
                normalized_name=normalize_patient_name(target_name),
                normalized_phone=normalize_phone_local(target_phone),
                account_id=None,
                relation="self",
                allergies=[],
                conditions=[],
            )
            session.add(walk_in)
            await session.commit()

        # Attempt registration (will fail with 409)
        res = await self.client.post("/auth/register", json={
            "name": target_name,
            "phone": target_phone,
            "password": "Password123!",
        })
        self.assertEqual(res.status_code, 409)

        # Verify no Profile was created for this phone
        async with AsyncSessionLocal() as session:
            stmt = select(Profile).where(Profile.phone == target_phone)
            user = (await session.execute(stmt)).scalar_one_or_none()
            self.assertIsNone(user, "Profile must NOT be created if registration fails")

    # 9. Correct patient creation
    async def test_09_correct_patient_creation(self):
        phone = "07788990011"
        name = "ضرغام علاء خليل"
        res = await self.client.post("/auth/register", json={
            "name": name,
            "phone": phone,
            "password": "Password123!",
        })
        self.assertEqual(res.status_code, 200)
        user_id = res.json()["data"]["user"]["id"]

        async with AsyncSessionLocal() as session:
            from app.core.security import normalize_phone_local, normalize_patient_name
            stmt = select(Patient).where(Patient.account_id == user_id)
            patient = (await session.execute(stmt)).scalar_one_or_none()
            self.assertIsNotNone(patient)
            self.assertEqual(patient.name, name)
            self.assertEqual(patient.phone, phone)
            self.assertEqual(patient.normalized_phone, normalize_phone_local(phone))
            self.assertEqual(patient.normalized_name, normalize_patient_name(name))
            self.assertEqual(patient.relation, "self")

    # 10. CORS OPTIONS preflight
    async def test_10_cors_options_preflight(self):
        res = await self.client.options(
            "/auth/register",
            headers={
                "Origin": "https://alrahma.ama8.uk",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization,idempotency-key",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("access-control-allow-origin"), "https://alrahma.ama8.uk")
        self.assertEqual(res.headers.get("access-control-allow-credentials"), "true")
        self.assertIn("POST", res.headers.get("access-control-allow-methods", ""))

    # 11. CORS headers on HTTP 500 responses
    async def test_11_cors_headers_on_http_500_responses(self):
        # Trigger an unhandled 500 by patching auth_service.register to raise unexpected RuntimeError
        # ASGITransport raise_app_exceptions=False allows receiving the 500 response instead of re-raising in test
        import httpx
        from httpx import ASGITransport
        from app.main import app

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as err_client:
            with patch("app.services.auth_service.register", side_effect=RuntimeError("Unexpected test crash")):
                res = await err_client.post(
                    "/auth/register",
                    json={
                        "name": "فاروق طه ياسين",
                        "phone": "07799001122",
                        "password": "Password123!",
                    },
                    headers={"Origin": "https://alrahma.ama8.uk"},
                )
                self.assertEqual(res.status_code, 500)
                self.assertEqual(res.headers.get("access-control-allow-origin"), "https://alrahma.ama8.uk")
                self.assertEqual(res.headers.get("access-control-allow-credentials"), "true")
                body = res.json()
                self.assertFalse(body["success"])
                self.assertEqual(body["code"], "internal_server_error")

    # 12. Registration response compatibility
    async def test_12_registration_response_compatibility(self):
        res = await self.client.post("/auth/register", json={
            "name": "بهاء مهدي صالح",
            "phone": "07700112233",
            "password": "Password123!",
        })
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("success", body)
        self.assertIn("data", body)
        data = body["data"]
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertIn("user", data)
        user = data["user"]
        self.assertIsInstance(user["id"], int)
        self.assertEqual(user["name"], "بهاء مهدي صالح")
        self.assertEqual(user["phone"], "07700112233")
        self.assertEqual(user["role"], "patient")
        self.assertIsNone(user["doctor_id"])


if __name__ == "__main__":
    unittest.main()
