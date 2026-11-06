import asyncio
import unittest
from datetime import date
from tests.conftest import get_test_client, auth_headers


class TestAppointmentConcurrency(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        self.patient_headers = auth_headers(user_id=5, role="patient")
        self.reception_headers = auth_headers(user_id=1, role="reception")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_20_concurrent_booking_requests_same_slot(self):
        """20 simultaneous concurrent booking requests to the exact same doctor and slot.
        Database-level GiST exclusion constraint and row locking guarantee that:
        - Exactly 1 request succeeds with 200 OK.
        - Exactly 19 requests are rejected with 409 Conflict ('slot_taken').
        """
        days_res = await self.client.get("/doctors/1/days", headers=self.patient_headers)
        days = days_res.json()["data"]
        future_work_days = [d["date"] for d in days if d["work"] and d["date"] > str(date.today())]
        self.assertTrue(len(future_work_days) >= 3)
        target_day = future_work_days[2]

        slots_res = await self.client.get(f"/doctors/1/slots?date={target_day}&kind=new", headers=self.patient_headers)
        available_slots = [s["time"] for s in slots_res.json()["data"] if s["available"]]
        self.assertTrue(len(available_slots) > 0)
        target_slot = available_slots[0]

        # Prepare 20 requests with unique idempotency keys
        tasks = []
        for i in range(20):
            payload = {
                "patient_id": 1,
                "doctor_id": 1,
                "date": target_day,
                "time": target_slot,
                "kind": "new",
                "pay": "clinic",
                "idempotency_key": f"concurrency-20-test-{target_day}-{target_slot}-{i}",
            }
            tasks.append(self.client.post("/appointments", json=payload, headers=self.patient_headers))

        responses = await asyncio.gather(*tasks)
        status_codes = [r.status_code for r in responses]

        success_count = status_codes.count(200)
        conflict_count = status_codes.count(409)

        self.assertEqual(success_count, 1, f"Expected exactly 1 successful booking, got {success_count}. Statuses: {status_codes}")
        self.assertEqual(conflict_count, 19, f"Expected 19 conflicts, got {conflict_count}")

    async def test_idempotency_key_replay_and_mismatch(self):
        """Replaying the exact same idempotency key returns the cached response.
        Using the same key with different payload returns 409 Conflict.
        """
        days_res = await self.client.get("/doctors/1/days", headers=self.patient_headers)
        days = days_res.json()["data"]
        future_work_days = [d["date"] for d in days if d["work"] and d["date"] > str(date.today())]
        target_day = future_work_days[3]

        slots_res = await self.client.get(f"/doctors/1/slots?date={target_day}&kind=new", headers=self.patient_headers)
        available_slots = [s["time"] for s in slots_res.json()["data"] if s["available"]]
        target_slot = available_slots[0]

        idemp_key = f"unique-idemp-key-{target_day}-{target_slot}"
        payload_original = {
            "patient_id": 1,
            "doctor_id": 1,
            "date": target_day,
            "time": target_slot,
            "kind": "new",
            "pay": "clinic",
            "idempotency_key": idemp_key,
        }

        # 1. Initial call -> 200 OK
        res1 = await self.client.post("/appointments", json=payload_original, headers=self.patient_headers)
        self.assertEqual(res1.status_code, 200)
        appt_id = res1.json()["data"]["appointment_id"]

        # 2. Replay with identical payload & header -> 200 OK returning same appointment ID
        headers_with_key = dict(self.patient_headers)
        headers_with_key["Idempotency-Key"] = idemp_key
        res_replay = await self.client.post("/appointments", json=payload_original, headers=headers_with_key)
        self.assertEqual(res_replay.status_code, 200)
        self.assertEqual(res_replay.json()["data"]["appointment_id"], appt_id)

        # 3. Same idempotency key with different payload -> 409 Conflict
        payload_different = {
            "patient_id": 1,
            "doctor_id": 1,
            "date": target_day,
            "time": available_slots[1],  # Different slot
            "kind": "new",
            "pay": "clinic",
            "idempotency_key": idemp_key,
        }
        res_mismatch = await self.client.post("/appointments", json=payload_different, headers=self.patient_headers)
        self.assertEqual(res_mismatch.status_code, 409)
        self.assertEqual(res_mismatch.json()["code"], "idempotency_conflict")

    async def test_cancellation_frees_slot_immediately(self):
        """Cancelling an appointment frees the slot immediately for other patients."""
        days_res = await self.client.get("/doctors/1/days", headers=self.patient_headers)
        days = days_res.json()["data"]
        future_work_days = [d["date"] for d in days if d["work"] and d["date"] > str(date.today())]
        target_day = future_work_days[4]

        slots_res = await self.client.get(f"/doctors/1/slots?date={target_day}&kind=new", headers=self.patient_headers)
        available_slots = [s["time"] for s in slots_res.json()["data"] if s["available"]]
        target_slot = available_slots[0]

        # Book
        payload = {
            "patient_id": 1,
            "doctor_id": 1,
            "date": target_day,
            "time": target_slot,
            "kind": "new",
            "pay": "clinic",
            "idempotency_key": f"free-slot-test-{target_day}-{target_slot}",
        }
        res_book = await self.client.post("/appointments", json=payload, headers=self.patient_headers)
        self.assertEqual(res_book.status_code, 200)
        appt_id = res_book.json()["data"]["appointment_id"]

        # Cancel
        res_cancel = await self.client.post(f"/appointments/{appt_id}/cancel", headers=self.patient_headers)
        self.assertEqual(res_cancel.status_code, 200)

        # Book same slot again -> must succeed!
        payload2 = {
            "patient_id": 1,
            "doctor_id": 1,
            "date": target_day,
            "time": target_slot,
            "kind": "new",
            "pay": "clinic",
            "idempotency_key": f"free-slot-test-rebook-{target_day}-{target_slot}",
        }
        res_rebook = await self.client.post("/appointments", json=payload2, headers=self.patient_headers)
        self.assertEqual(res_rebook.status_code, 200)


if __name__ == "__main__":
    unittest.main()
