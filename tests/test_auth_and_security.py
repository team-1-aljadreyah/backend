import unittest
import asyncio
from tests.conftest import get_test_client, auth_headers


class TestAuthAndSecurity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_health_check(self):
        res = await self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")

    async def test_unauthenticated_access_blocked(self):
        # 1. Unauthenticated user cannot access protected routes
        for endpoint in ["/settings", "/me/family", "/prescriptions", "/ledger", "/lab/orders"]:
            res = await self.client.get(endpoint)
            self.assertEqual(res.status_code, 401, f"Endpoint {endpoint} should require authentication")

    async def test_login_success_and_failure(self):
        # Valid login
        res = await self.client.post("/auth/login", json={"phone": "07800000005", "password": "password123"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertIn("access_token", body["data"])
        self.assertEqual(body["data"]["user"]["role"], "patient")

        # Invalid login
        bad_res = await self.client.post("/auth/login", json={"phone": "07800000005", "password": "wrong_password"})
        self.assertEqual(bad_res.status_code, 401)
        self.assertFalse(bad_res.json()["success"])

    async def test_public_registration_enforces_patient_role(self):
        # 7. A patient cannot assign themselves an administrative role
        new_phone = "07712345678"
        reg_payload = {
            "name": "Test Public User",
            "phone": new_phone,
            "password": "password123",
            "role": "manager",  # Malicious attempt to self-assign manager role
        }
        res = await self.client.post("/auth/register", json=reg_payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        # Role must strictly be 'patient'
        self.assertEqual(body["data"]["user"]["role"], "patient")

    async def test_token_refresh(self):
        # Obtain tokens
        login_res = await self.client.post("/auth/login", json={"phone": "07800000005", "password": "password123"})
        refresh_token = login_res.json()["data"]["refresh_token"]

        # Call /auth/refresh
        ref_res = await self.client.post("/auth/refresh", json={"refresh_token": refresh_token})
        self.assertEqual(ref_res.status_code, 200)
        self.assertTrue(ref_res.json()["success"])
        self.assertIn("access_token", ref_res.json()["data"])

    async def test_role_based_access_control(self):
        patient_headers = auth_headers(user_id=5, role="patient")
        reception_headers = auth_headers(user_id=1, role="reception")
        doctor1_headers = auth_headers(user_id=2, role="doctor")
        doctor2_headers = auth_headers(user_id=3, role="doctor")
        pharmacy_headers = auth_headers(user_id=4, role="pharmacy")
        accountant_headers = auth_headers(user_id=8, role="accountant")

        # 3. Doctor cannot access unauthorized doctor queues
        res = await self.client.get("/doctors/2/queue", headers=doctor1_headers)
        self.assertEqual(res.status_code, 403, "Doctor 1 cannot access Doctor 2 queue")

        # 4. Pharmacist cannot access accounting ledger
        res = await self.client.get("/ledger", headers=pharmacy_headers)
        self.assertEqual(res.status_code, 403, "Pharmacist cannot access ledger")

        # 5. Receptionist cannot modify protected clinical diagnoses
        finish_payload = {
            "diagnosis": "Hacked",
            "internal_note": "",
            "medicines": [],
            "test_ids": [],
            "procedure_ids": [],
            "follow_up_days": None,
        }
        res = await self.client.post("/appointments/1/finish", json=finish_payload, headers=reception_headers)
        self.assertEqual(res.status_code, 403, "Receptionist cannot finish visit")

        # 6. Accountant cannot modify clinical diagnoses or alerts
        alerts_payload = {"allergies": [], "conditions": [], "blood_type": "O+"}
        res = await self.client.put("/patients/1/alerts", json=alerts_payload, headers=accountant_headers)
        self.assertEqual(res.status_code, 403, "Accountant cannot modify alerts")


if __name__ == "__main__":
    unittest.main()
