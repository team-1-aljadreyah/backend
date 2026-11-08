import unittest
import io
from datetime import date, timedelta
from tests.conftest import get_test_client, auth_headers


class TestOnlinePaymentsAndWelfare(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        self.patient_headers = auth_headers(5, "patient")
        self.reception_headers = auth_headers(1, "reception")
        self.manager_headers = auth_headers(6, "manager")
        self.doctor_headers = auth_headers(2, "doctor")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_welfare_submission_review_and_discount(self):
        # 1. Submit welfare card photo and number with valid JPEG header
        fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50)
        files = {"photo": ("card.jpg", fake_photo, "image/jpeg")}
        data = {"card_number": "WELFARE-12345"}

        sub_res = await self.client.post(
            "/patients/1/welfare",
            data=data,
            files=files,
            headers=self.patient_headers,
        )
        self.assertEqual(sub_res.status_code, 200)
        welfare_data = sub_res.json()["data"]
        self.assertEqual(welfare_data["card_number"], "WELFARE-12345")
        self.assertEqual(welfare_data["status"], "pending")
        req_id = welfare_data["id"]

        # 2. Reception lists pending welfare
        list_res = await self.client.get("/welfare?status=pending", headers=self.reception_headers)
        self.assertEqual(list_res.status_code, 200)
        items = list_res.json()["data"]
        self.assertTrue(any(w["id"] == req_id for w in items))

        # 3. Reception approves welfare
        future_date = (date.today() + timedelta(days=365)).isoformat()
        review_res = await self.client.post(
            f"/welfare/{req_id}/review",
            json={"approve": True, "valid_until": future_date},
            headers=self.reception_headers,
        )
        self.assertEqual(review_res.status_code, 200)
        self.assertEqual(review_res.json()["data"]["status"], "approved")

        # 4. Check booking rules reflect welfare discount percent
        rules_res = await self.client.get("/patients/1/booking-rules", headers=self.patient_headers)
        self.assertEqual(rules_res.status_code, 200)
        self.assertGreater(rules_res.json()["data"]["welfare_percent"], 0)

        # 5. Check family welfare
        my_welfare_res = await self.client.get("/me/welfare", headers=self.patient_headers)
        self.assertEqual(my_welfare_res.status_code, 200)
        self.assertTrue(len(my_welfare_res.json()["data"]) >= 1)

    async def test_online_payment_session_and_settlement(self):
        # Book an appointment on the next available working day
        book_date = None
        slot_time = None
        for day_offset in range(1, 10):
            cand_date = (date.today() + timedelta(days=day_offset)).isoformat()
            slots_res = await self.client.get(f"/doctors/1/slots?date={cand_date}&kind=new", headers=self.patient_headers)
            if slots_res.status_code == 200:
                avail = [s for s in slots_res.json()["data"] if s["available"]]
                if avail:
                    book_date = cand_date
                    slot_time = avail[0]["time"]
                    break

        self.assertIsNotNone(book_date, "Must find an available slot for doctor 1")
        self.assertIsNotNone(slot_time, "Must find an available slot time")

        book_payload = {
            "patient_id": 1,
            "doctor_id": 1,
            "date": book_date,
            "time": slot_time,
            "kind": "new",
            "pay": "none",
            "idempotency_key": "test_pay_session_book_1",
        }
        b_res = await self.client.post("/appointments", json=book_payload, headers=self.patient_headers)
        self.assertEqual(b_res.status_code, 200)
        appt_id = b_res.json()["data"]["appointment_id"]

        # Create online payment session
        pay_session_res = await self.client.post(
            f"/appointments/{appt_id}/payments",
            json={"idempotency_key": "pay_key_001", "return_url": "/account/appointments"},
            headers=self.patient_headers,
        )
        self.assertEqual(pay_session_res.status_code, 200)
        p_data = pay_session_res.json()["data"]
        self.assertEqual(p_data["status"], "created")
        self.assertIn("form_url", p_data)
        payment_id = p_data["payment_id"]

        # Idempotency check: same call returns same session
        pay_session_dup = await self.client.post(
            f"/appointments/{appt_id}/payments",
            json={"idempotency_key": "pay_key_001", "return_url": "/account/appointments"},
            headers=self.patient_headers,
        )
        self.assertEqual(pay_session_dup.status_code, 200)
        self.assertEqual(pay_session_dup.json()["data"]["payment_id"], payment_id)

        # Query payment status
        status_res = await self.client.get(f"/payments/{payment_id}", headers=self.patient_headers)
        self.assertEqual(status_res.status_code, 200)
        self.assertEqual(status_res.json()["data"]["status"], "created")

        # Settle payment session as success
        sim_res = await self.client.post(
            f"/payments/{payment_id}/simulate",
            json={"outcome": "success"},
            headers=self.patient_headers,
        )
        self.assertEqual(sim_res.status_code, 200)
        self.assertEqual(sim_res.json()["data"]["status"], "success")

    async def test_paginated_payment_history(self):
        # Query GET /me/payments
        res = await self.client.get("/me/payments?limit=20&offset=0", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()["data"]
        self.assertIn("items", body)
        self.assertIn("total", body)
        self.assertIsInstance(body["items"], list)
        self.assertIsInstance(body["total"], int)

    async def test_upcoming_appointments(self):
        # Reception lists upcoming appointments
        res = await self.client.get("/appointments/upcoming?days=7&include_today=true", headers=self.reception_headers)
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json()["data"], list)

    async def test_password_change_validation_code(self):
        # Wrong password must return 422 wrong_password, NEVER 401
        res = await self.client.post(
            "/auth/password/change",
            json={"current_password": "completely_wrong_pw", "new_password": "NewSecretPassword123!"},
            headers=self.patient_headers,
        )
        self.assertEqual(res.status_code, 422)
        body = res.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], "wrong_password")


if __name__ == "__main__":
    unittest.main()
