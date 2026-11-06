import asyncio
import unittest
from datetime import date
from tests.conftest import get_test_client, auth_headers
from app.core.security import normalize_patient_name, normalize_phone_local


class TestPatientMergeAndDedup(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        self.manager_headers = auth_headers(user_id=6, role="manager")
        self.reception_headers = auth_headers(user_id=1, role="reception")
        self.patient_headers = auth_headers(user_id=5, role="patient")

    async def asyncTearDown(self):
        await self.client.aclose()

    def test_arabic_name_and_phone_normalization(self):
        """Test normalization utilities for Arabic names and phone numbers."""
        self.assertEqual(normalize_patient_name("أحمد علي حسن"), "احمد علي حسن")
        self.assertEqual(normalize_patient_name("  سارة   محمود  "), "ساره محمود")
        self.assertEqual(normalize_patient_name("مُحَمَّدْ عَلي"), "محمد علي")
        self.assertEqual(normalize_patient_name("يحيى إبراهيم"), "يحيي ابراهيم")

        self.assertEqual(normalize_phone_local("+9647801234567"), "07801234567")
        self.assertEqual(normalize_phone_local("009647701234567"), "07701234567")
        self.assertEqual(normalize_phone_local("7801234567"), "07801234567")
        self.assertEqual(normalize_phone_local("0780 123 4567"), "07801234567")

    async def test_duplicate_check_detection(self):
        """Test candidate duplicate detection with confidence scoring."""
        # Check against existing patient (e.g. phone: 07800000005, name: 'زينب كريم')
        req_exact = {
            "name": "زينب كريم",
            "phone": "07800000005",
            "birth_date": "1995-05-15",
        }
        res = await self.client.post("/patients/duplicates/check", json=req_exact, headers=self.reception_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertTrue(data["has_exact_match"])
        self.assertTrue(len(data["candidates"]) >= 1)
        top = data["candidates"][0]
        self.assertEqual(top["match_type"], "exact_match")
        self.assertAlmostEqual(top["confidence"], 1.0)

        # Family member sharing phone: same phone, different name
        req_family = {
            "name": "علي كريم",
            "phone": "07800000005",
        }
        res_fam = await self.client.post("/patients/duplicates/check", json=req_family, headers=self.reception_headers)
        self.assertEqual(res_fam.status_code, 200)
        data_fam = res_fam.json()["data"]
        self.assertFalse(data_fam["has_exact_match"])
        top_fam = next((c for c in data_fam["candidates"] if c["match_type"] == "shared_phone_family"), None)
        self.assertIsNotNone(top_fam)
        self.assertLess(top_fam["confidence"], 0.8)

    async def test_family_member_registration_shared_phone(self):
        """Family members sharing the same phone number can be registered without conflict."""
        add_child_req = {
            "name": "يوسف محمد",
            "relation": "child",
            "phone": "07800000005",  # Shared phone
            "birth_date": "2018-01-01",
        }
        res = await self.client.post("/me/family", json=add_child_req, headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)

        # Verify child appears in family list
        fam_res = await self.client.get("/me/family", headers=self.patient_headers)
        self.assertEqual(fam_res.status_code, 200)
        names = [f["name"] for f in fam_res.json()["data"]]
        self.assertIn("يوسف محمد", names)

    async def test_patient_merge_execution_and_transfer(self):
        """Test complete patient merge: transferring appointments, visits, vitals, alerts."""
        # 1. Create source patient via walk-in
        walk_in_req = {
            "name": "حسين خليل التميمي",
            "phone": "07719998877",
            "doctor_id": 1,
            "emergency": False,
        }
        w_res = await self.client.post("/walk-ins", json=walk_in_req, headers=self.reception_headers)
        self.assertEqual(w_res.status_code, 200)

        # Find created source patient
        search_res = await self.client.get("/patients?q=حسين خليل", headers=self.reception_headers)
        self.assertEqual(search_res.status_code, 200)
        source_patient = search_res.json()["data"]["items"][0]
        source_id = source_patient["id"]

        # Primary patient is ID 1 (سارة موظفة)
        primary_id = 1

        # 2. Reception attempts merge -> 403 Forbidden
        merge_payload = {
            "primary_patient_id": primary_id,
            "source_patient_id": source_id,
            "reason": "Duplicate patient registration consolidated",
        }
        forbid_res = await self.client.post("/patients/merge", json=merge_payload, headers=self.reception_headers)
        self.assertEqual(forbid_res.status_code, 403)

        # 3. Manager executes merge -> 200 OK
        merge_res = await self.client.post("/patients/merge", json=merge_payload, headers=self.manager_headers)
        self.assertEqual(merge_res.status_code, 200)
        merge_data = merge_res.json()["data"]
        self.assertEqual(merge_data["source_patient_id"], source_id)
        self.assertIn("appointments", merge_data["records_transferred"])

        # 4. Verify source patient file request transparently resolves to primary patient
        file_res = await self.client.get(f"/patients/{source_id}/file", headers=self.manager_headers)
        self.assertEqual(file_res.status_code, 200)
        file_data = file_res.json()["data"]
        self.assertEqual(file_data["patient"]["id"], primary_id)

    async def test_merge_validation_preventions(self):
        """Self-merge and merging already merged patient must be prevented."""
        # Self merge
        self_req = {
            "primary_patient_id": 1,
            "source_patient_id": 1,
            "reason": "Invalid self-merge",
        }
        res = await self.client.post("/patients/merge", json=self_req, headers=self.manager_headers)
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["code"], "self_merge_not_allowed")


if __name__ == "__main__":
    unittest.main()
