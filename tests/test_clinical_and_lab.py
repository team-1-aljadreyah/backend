import unittest
from datetime import date
from tests.conftest import get_test_client, auth_headers


class TestClinicalAndLab(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        self.patient_headers = auth_headers(user_id=5, role="patient")
        self.doctor_headers = auth_headers(user_id=2, role="doctor")
        self.reception_headers = auth_headers(user_id=1, role="reception")
        self.lab_headers = auth_headers(user_id=7, role="lab")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_vitals_recording_and_retrieval(self):
        # Create walk-in to get an active appointment today
        w_res = await self.client.post(
            "/walk-ins",
            json={"name": "Vitals Patient Ali", "phone": "07711223344", "doctor_id": 1, "emergency": False},
            headers=self.reception_headers,
        )
        self.assertEqual(w_res.status_code, 200)

        # Get queue to identify appointment id
        q_res = await self.client.get("/doctors/1/queue", headers=self.doctor_headers)
        appt = next(a for a in q_res.json()["data"] if a["patient_name"] == "Vitals Patient Ali")
        appt_id = appt["id"]
        patient_id = appt["patient_id"]

        # Record vitals
        vitals_payload = {
            "systolic": 120,
            "diastolic": 80,
            "temperature": 37.0,
            "pulse": 72,
            "spo2": 98.5,
            "weight": 70.0,
            "height": 175.0,
        }
        v_res = await self.client.put(f"/appointments/{appt_id}/vitals", json=vitals_payload, headers=self.reception_headers)
        self.assertEqual(v_res.status_code, 200)
        self.assertEqual(v_res.json()["data"]["systolic"], 120)

        # Fetch patient vitals
        pv_res = await self.client.get(f"/patients/{patient_id}/vitals", headers=self.doctor_headers)
        self.assertEqual(pv_res.status_code, 200)
        self.assertTrue(len(pv_res.json()["data"]) > 0)
        self.assertEqual(pv_res.json()["data"][0]["systolic"], 120)

    async def test_consultation_completion_and_lab_flow(self):
        # 1. Start consultation
        w_res = await self.client.post(
            "/walk-ins",
            json={"name": "Lab Test Patient", "phone": "07755667788", "doctor_id": 1, "emergency": False},
            headers=self.reception_headers,
        )
        q_res = await self.client.get("/doctors/1/queue", headers=self.doctor_headers)
        appt = next(a for a in q_res.json()["data"] if a["patient_name"] == "Lab Test Patient")
        appt_id = appt["id"]

        start_res = await self.client.post(f"/appointments/{appt_id}/start", headers=self.doctor_headers)
        self.assertEqual(start_res.status_code, 200)

        # 2. Finish visit requesting a Blood Sugar test (service_id = 1)
        finish_payload = {
            "diagnosis": "Acute Gastritis",
            "internal_note": "Confidential physician note",
            "medicines": [{"name": "Omeprazole 20mg", "dose": "1/1", "days": 14}],
            "test_ids": [1],
            "procedure_ids": [],
            "follow_up_days": 14,
        }
        fin_res = await self.client.post(f"/appointments/{appt_id}/finish", json=finish_payload, headers=self.doctor_headers)
        self.assertEqual(fin_res.status_code, 200)

        # 3. Lab technician views order
        orders_res = await self.client.get("/lab/orders", headers=self.lab_headers)
        self.assertEqual(orders_res.status_code, 200)
        orders = orders_res.json()["data"]
        target_order = next((o for o in orders if o["patient_name"] == "Lab Test Patient"), None)
        self.assertIsNotNone(target_order)
        self.assertEqual(target_order["status"], "requested")

        # 4. Lab enters result readings
        result_payload = {
            "type": "values",
            "rows": [{"name": "Fasting glucose", "value": 95, "unit": "mg/dL", "ref_low": 70, "ref_high": 110}],
            "sample": "blood",
            "note": "Normal fasting reading",
        }
        save_res = await self.client.put(f"/lab/orders/{target_order['id']}/result", json=result_payload, headers=self.lab_headers)
        self.assertEqual(save_res.status_code, 200)

        # 5. Confirm result
        conf_res = await self.client.post(f"/lab/orders/{target_order['id']}/confirm", headers=self.lab_headers)
        self.assertEqual(conf_res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
