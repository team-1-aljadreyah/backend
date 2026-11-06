import asyncio
import unittest
from datetime import date
from tests.conftest import get_test_client, auth_headers


class TestConcurrencyAndIdempotency(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        self.patient_headers = auth_headers(user_id=5, role="patient")
        self.reception_headers = auth_headers(user_id=1, role="reception")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_concurrent_slot_booking(self):
        """Two simultaneous requests attempting to book the exact same doctor and slot.
        Only one must succeed (200), and the other must be rejected with 409 Conflict.
        """
        days_res = await self.client.get("/doctors/1/days", headers=self.patient_headers)
        days = days_res.json()["data"]
        # Pick the 3rd working day to avoid interference with other tests
        working_days = [d["date"] for d in days if d["work"] and d["date"] > str(date.today())]
        self.assertTrue(len(working_days) >= 2)
        target_day = working_days[1]

        slots_res = await self.client.get(f"/doctors/1/slots?date={target_day}&kind=new", headers=self.patient_headers)
        available_slots = [s["time"] for s in slots_res.json()["data"] if s["available"]]
        self.assertTrue(len(available_slots) > 0)
        target_slot = available_slots[0]

        payload_1 = {
            "patient_id": 1,
            "doctor_id": 1,
            "date": target_day,
            "time": target_slot,
            "kind": "new",
            "pay": "clinic",
            "idempotency_key": f"concurrent-req-1-{target_day}-{target_slot}",
        }
        payload_2 = {
            "patient_id": 1,
            "doctor_id": 1,
            "date": target_day,
            "time": target_slot,
            "kind": "new",
            "pay": "clinic",
            "idempotency_key": f"concurrent-req-2-{target_day}-{target_slot}",
        }

        # Fire both concurrently
        res1, res2 = await asyncio.gather(
            self.client.post("/appointments", json=payload_1, headers=self.patient_headers),
            self.client.post("/appointments", json=payload_2, headers=self.patient_headers),
        )

        status_codes = sorted([res1.status_code, res2.status_code])
        self.assertEqual(status_codes, [200, 409], f"Expected one 200 and one 409, got {status_codes}")

    async def test_idempotent_appointment_booking(self):
        """Sending the exact same idempotency_key must succeed and produce only a single appointment."""
        days_res = await self.client.get("/doctors/1/days", headers=self.patient_headers)
        days = days_res.json()["data"]
        working_days = [d["date"] for d in days if d["work"] and d["date"] > str(date.today())]
        target_day = working_days[-1]  # Pick last working day

        slots_res = await self.client.get(f"/doctors/1/slots?date={target_day}&kind=new", headers=self.patient_headers)
        available_slots = [s["time"] for s in slots_res.json()["data"] if s["available"]]
        target_slot = available_slots[-1]

        idempotency_key = f"idempotent-key-{target_day}-{target_slot}"
        payload = {
            "patient_id": 1,
            "doctor_id": 1,
            "date": target_day,
            "time": target_slot,
            "kind": "new",
            "pay": "clinic",
            "idempotency_key": idempotency_key,
        }

        # First call
        res1 = await self.client.post("/appointments", json=payload, headers=self.patient_headers)
        self.assertEqual(res1.status_code, 200)

        # Duplicate call with identical idempotency key
        res2 = await self.client.post("/appointments", json=payload, headers=self.patient_headers)
        self.assertEqual(res2.status_code, 200)

        # Verify that only 1 appointment exists for that day & slot
        my_appts_res = await self.client.get("/me/appointments", headers=self.patient_headers)
        self.assertEqual(my_appts_res.status_code, 200)
        matching = [
            a for a in my_appts_res.json()["data"]
            if a["date"] == target_day and a["time"] == target_slot and a["status"] != "cancelled"
        ]
        self.assertEqual(len(matching), 1, "Expected exactly 1 active appointment for this slot")

    async def test_idempotent_payment_cash(self):
        """Cash payments with identical idempotency key should not double charge."""
        # Create walk-in to get fresh appointment
        w_res = await self.client.post(
            "/walk-ins",
            json={"name": "Idempotent Payer One", "phone": "07700001122", "doctor_id": 1, "emergency": False},
            headers=self.reception_headers,
        )
        self.assertEqual(w_res.status_code, 200)

        # Get queue to find appt id
        q_res = await self.client.get("/doctors/1/queue", headers=self.reception_headers)
        appt = next(a for a in q_res.json()["data"] if a["patient_name"] == "Idempotent Payer One")
        appt_id = appt["id"]

        idem_key = f"pay-idem-key-{appt_id}"
        pay_payload = {
            "amount": 25000.0,
            "currency": "IQD",
            "idempotency_key": idem_key,
        }

        # First payment call
        res1 = await self.client.post(f"/appointments/{appt_id}/pay-cash", json=pay_payload, headers=self.reception_headers)
        self.assertEqual(res1.status_code, 200)

        # Duplicate payment call with identical idempotency key
        res2 = await self.client.post(f"/appointments/{appt_id}/pay-cash", json=pay_payload, headers=self.reception_headers)
        self.assertEqual(res2.status_code, 200)

        # Check today's invoices to confirm balance is 0 and exactly 25,000 was paid (not 50,000)
        inv_res = await self.client.get("/invoices/today", headers=self.reception_headers)
        self.assertEqual(inv_res.status_code, 200)
        inv = next(i for i in inv_res.json()["data"] if i["appointment_id"] == appt_id)
        self.assertEqual(inv["money"]["paid"]["IQD"], 25000.0)
        self.assertEqual(inv["money"]["balance"]["IQD"], 0.0)


if __name__ == "__main__":
    unittest.main()
