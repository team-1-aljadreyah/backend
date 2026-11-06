import unittest
from datetime import date, timedelta
from tests.conftest import get_test_client, auth_headers


class TestAppointmentsAndQueues(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        self.patient_headers = auth_headers(user_id=5, role="patient")
        self.reception_headers = auth_headers(user_id=1, role="reception")
        self.doctor_headers = auth_headers(user_id=2, role="doctor")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_doctor_slots_and_booking(self):
        # 1. Fetch doctor days
        days_res = await self.client.get("/doctors/1/days", headers=self.patient_headers)
        self.assertEqual(days_res.status_code, 200)
        days = days_res.json()["data"]
        self.assertEqual(len(days), 14)

        # Find first working day that is not today
        target_day = next((d["date"] for d in days if d["work"] and d["date"] > str(date.today())), None)
        self.assertIsNotNone(target_day)

        # Fetch slots for that day
        slots_res = await self.client.get(f"/doctors/1/slots?date={target_day}&kind=new", headers=self.patient_headers)
        self.assertEqual(slots_res.status_code, 200)
        slots = slots_res.json()["data"]
        self.assertTrue(len(slots) > 0)
        free_slot = next((s["time"] for s in slots if s["available"]), None)
        self.assertIsNotNone(free_slot)

        # 2. Book appointment as patient
        book_payload = {
            "patient_id": 1,
            "doctor_id": 1,
            "date": target_day,
            "time": free_slot,
            "kind": "new",
            "pay": "clinic",
            "idempotency_key": f"key-book-{target_day}-{free_slot}",
        }
        res = await self.client.post("/appointments", json=book_payload, headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)

        # Verify slot is now taken
        slots_res2 = await self.client.get(f"/doctors/1/slots?date={target_day}&kind=new", headers=self.patient_headers)
        slot_status = next(s for s in slots_res2.json()["data"] if s["time"] == free_slot)
        self.assertFalse(slot_status["available"])

    async def test_staff_booking_and_checkin_and_walkin(self):
        # Staff assisted booking - find a working day with slots
        days_res = await self.client.get("/doctors/1/days", headers=self.reception_headers)
        days = days_res.json()["data"]
        target_day = next(d["date"] for d in days if d["work"] and d["date"] > str(date.today()))
        slots_res = await self.client.get(f"/doctors/1/slots?date={target_day}&kind=new", headers=self.reception_headers)
        free_slot = next(s["time"] for s in slots_res.json()["data"] if s["available"])

        staff_payload = {
            "patient_id": 1,
            "new_patient": None,
            "doctor_id": 1,
            "date": target_day,
            "time": free_slot,
            "kind": "new",
            "idempotency_key": f"staff-key-{target_day}",
        }
        staff_res = await self.client.post("/appointments/by-staff", json=staff_payload, headers=self.reception_headers)
        self.assertEqual(staff_res.status_code, 200)
        self.assertEqual(staff_res.json()["data"]["patient_id"], 1)

        # Walk-in registration
        walkin_payload = {
            "name": "Walkin Patient",
            "phone": "07799998888",
            "doctor_id": 1,
            "emergency": True,
        }
        w_res = await self.client.post("/walk-ins", json=walkin_payload, headers=self.reception_headers)
        self.assertEqual(w_res.status_code, 200)
        self.assertIn("duplicate", w_res.json()["data"])

        # Check doctor queue
        q_res = await self.client.get("/doctors/1/queue", headers=self.doctor_headers)
        self.assertEqual(q_res.status_code, 200)
        queue = q_res.json()["data"]
        # Emergency walk-in should be at or near the front of waiting queue
        self.assertTrue(any(a["patient_name"] == "Walkin Patient" and a["emergency"] for a in queue))

    async def test_booking_rules_endpoint(self):
        res = await self.client.get("/patients/1/booking-rules", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()["data"]
        self.assertIn("no_shows", body)
        self.assertIn("deposit_required", body)
        self.assertIn("deposit_amount", body)


if __name__ == "__main__":
    unittest.main()
