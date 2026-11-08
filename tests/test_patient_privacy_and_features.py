import unittest
from tests.conftest import get_test_client, auth_headers
from app.core.security import validate_three_part_name, extract_name_parts
from app.core.exceptions import UnprocessableEntityException


class TestPatientPrivacyAndFeatures(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        self.reception_headers = auth_headers(user_id=1, role="reception")
        self.doctor1_headers = auth_headers(user_id=2, role="doctor")
        self.doctor2_headers = auth_headers(user_id=3, role="doctor")
        self.manager_headers = auth_headers(user_id=6, role="manager")
        self.patient_headers = auth_headers(user_id=5, role="patient")

    async def asyncTearDown(self):
        await self.client.aclose()

    def test_three_part_name_extraction_and_validation(self):
        # Valid 3-part names
        valid_samples = [
            "علي حسن علي",
            "د. علي حسن علي",
            "د. عبد الكريم محمد علي",
            "أبو بكر سالم حسن",
            "نور الدين علي حسن",
            "أحمد فضل الله حسن",
            "عبد الله عبد الرحمن عبد العزيز",
            "محمد علي حسن جاسم",
            "John Michael Doe",
        ]
        for name in valid_samples:
            parts = extract_name_parts(name)
            self.assertEqual(len(parts), 3, f"Expected 3 parts for '{name}', got: {parts}")
            # Should not raise
            validate_three_part_name(name)

        # Invalid names (too few or too many parts)
        invalid_samples = [
            "علي حسن",
            "علي",
            "د. علي",
            "علي حسن كريم جاسم سعيد",
            "Jane Doe",
        ]
        for name in invalid_samples:
            parts = extract_name_parts(name)
            self.assertNotEqual(len(parts), 3, f"Expected != 3 parts for '{name}', got: {parts}")
            with self.assertRaises(UnprocessableEntityException):
                validate_three_part_name(name)

    async def test_reception_medical_file_privacy(self):
        # Patient 4 has conditions and allergies in seed data
        # Reception accessing file
        rec_res = await self.client.get("/patients/4/file", headers=self.reception_headers)
        self.assertEqual(rec_res.status_code, 200)
        data = rec_res.json()["data"]

        # Reception MUST NOT see medical visits, diagnoses, prescriptions, tests or alerts
        self.assertEqual(data["visits"], [])
        self.assertEqual(data["alerts"]["allergies"], [])
        self.assertEqual(data["alerts"]["conditions"], [])
        self.assertIsNone(data["alerts"]["blood_type"])

        # Manager gets the full file with alerts
        mgr_res = await self.client.get("/patients/4/file", headers=self.manager_headers)
        self.assertEqual(mgr_res.status_code, 200)
        mgr_data = mgr_res.json()["data"]
        self.assertIn("Aspirin", mgr_data["alerts"]["allergies"])

    async def test_doctor_file_access_restriction(self):
        # Create a walk-in appointment with doctor 1 for a new patient
        w_res = await self.client.post(
            "/walk-ins",
            json={
                "name": "فاضل عباس حميد",
                "phone": "07788112233",
                "doctor_id": 1,
                "emergency": False,
            },
            headers=self.reception_headers,
        )
        self.assertEqual(w_res.status_code, 200)

        # Get patient id from search
        search_res = await self.client.get("/patients?q=07788112233", headers=self.reception_headers)
        patient_id = search_res.json()["data"]["items"][0]["id"]

        # Doctor 1 (who has an appointment with this patient) can open the file
        doc1_res = await self.client.get(f"/patients/{patient_id}/file", headers=self.doctor1_headers)
        self.assertEqual(doc1_res.status_code, 200)

        # Doctor 2 (who has NO appointment with this patient) is blocked with 403 Forbidden
        doc2_res = await self.client.get(f"/patients/{patient_id}/file", headers=self.doctor2_headers)
        self.assertEqual(doc2_res.status_code, 403)
        self.assertEqual(doc2_res.json()["code"], "forbidden")

        # Manager can always open the file
        mgr_res = await self.client.get(f"/patients/{patient_id}/file", headers=self.manager_headers)
        self.assertEqual(mgr_res.status_code, 200)

    async def test_audit_log_records_file_open(self):
        res = await self.client.get("/patients/1/file", headers=self.manager_headers)
        self.assertEqual(res.status_code, 200)

        # Check audit log
        audit_res = await self.client.get("/audit", headers=self.manager_headers)
        self.assertEqual(audit_res.status_code, 200)
        entries = audit_res.json()["data"]["items"]
        file_open_logs = [e for e in entries if e["action"] == "file.open"]
        self.assertGreater(len(file_open_logs), 0)

    async def test_users_list_paging_and_search(self):
        # 0. Plain list (for Front api.listStaff)
        res_plain = await self.client.get("/users", headers=self.manager_headers)
        self.assertEqual(res_plain.status_code, 200)
        users_arr = res_plain.json()["data"]
        self.assertIsInstance(users_arr, list)
        self.assertGreater(len(users_arr), 0)

        # 1. Paged list
        res_page = await self.client.get("/users?limit=3&offset=0", headers=self.manager_headers)
        self.assertEqual(res_page.status_code, 200)
        data = res_page.json()["data"]
        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertLessEqual(len(data["items"]), 3)
        self.assertGreaterEqual(data["total"], 3)

        # 2. Search by phone
        res_search_phone = await self.client.get("/users?search=07800000001", headers=self.manager_headers)
        self.assertEqual(res_search_phone.status_code, 200)
        data_p = res_search_phone.json()["data"]
        self.assertEqual(len(data_p["items"]), 1)
        self.assertEqual(data_p["items"][0]["phone"], "07800000001")

        # 3. Search by name
        res_search_name = await self.client.get("/users?search=سارة", headers=self.manager_headers)
        self.assertEqual(res_search_name.status_code, 200)
        data_n = res_search_name.json()["data"]
        self.assertGreater(len(data_n["items"]), 0)

        # 4. Filter by role (exact: 'doctor')
        res_role_doctor = await self.client.get("/users?role=doctor", headers=self.manager_headers)
        self.assertEqual(res_role_doctor.status_code, 200)
        data_doc = res_role_doctor.json()["data"]
        self.assertIn("items", data_doc)
        self.assertGreater(len(data_doc["items"]), 0)
        self.assertTrue(all(u["role"] == "doctor" for u in data_doc["items"]))

        # 5. Filter by job with phrase ('doctors only')
        res_job_doc_phrase = await self.client.get("/users?job=doctors%20only", headers=self.manager_headers)
        self.assertEqual(res_job_doc_phrase.status_code, 200)
        data_phrase = res_job_doc_phrase.json()["data"]
        self.assertGreater(len(data_phrase["items"]), 0)
        self.assertTrue(all(u["role"] == "doctor" for u in data_phrase["items"]))

        # 6. Filter by Arabic role ('الأطباء')
        res_job_ar = await self.client.get("/users?role=الأطباء", headers=self.manager_headers)
        self.assertEqual(res_job_ar.status_code, 200)
        data_ar = res_job_ar.json()["data"]
        self.assertGreater(len(data_ar["items"]), 0)
        self.assertTrue(all(u["role"] == "doctor" for u in data_ar["items"]))

        # 7. Combined role filter and search
        res_comb = await self.client.get("/users?role=doctor&search=0780", headers=self.manager_headers)
        self.assertEqual(res_comb.status_code, 200)
        data_comb = res_comb.json()["data"]
        self.assertTrue(all(u["role"] == "doctor" for u in data_comb["items"]))

        # 8. All roles filter ('all')
        res_all = await self.client.get("/users?role=all", headers=self.manager_headers)
        self.assertEqual(res_all.status_code, 200)
        data_all = res_all.json()["data"]
        roles_present = {u["role"] for u in data_all["items"]}
        self.assertGreater(len(roles_present), 1)

    async def test_doctor_schedule_custom_working_hours(self):
        # 1. Inspect existing schedules
        sched_res = await self.client.get("/doctors/schedules", headers=self.manager_headers)
        self.assertEqual(sched_res.status_code, 200)
        schedules = sched_res.json()["data"]
        self.assertGreater(len(schedules), 0)
        first_doc = schedules[0]
        # Days should contain start and end
        work_day = next(d for d in first_doc["days"] if d is not None)
        self.assertIn("start", work_day)
        self.assertIn("end", work_day)

        # 2. Update doctor schedule with custom working hours
        new_days = list(first_doc["days"])
        # Set Sunday (day 0) to custom start 10:00 and end 12:00
        new_days[0] = {
            "branch": "main",
            "shift": "morning",
            "start": "10:00",
            "end": "12:00",
        }
        update_payload = {
            "fee": first_doc["doctor"]["fee"],
            "clinic_percent": first_doc["clinic_percent"],
            "service_percent": first_doc["service_percent"],
            "new_minutes": 30,
            "followup_minutes": 15,
            "days": new_days,
        }
        put_res = await self.client.put(f"/doctors/{first_doc['doctor']['id']}/schedule", json=update_payload, headers=self.manager_headers)
        self.assertEqual(put_res.status_code, 200)

        # 3. Verify updated schedule returns the custom start/end
        verify_res = await self.client.get("/doctors/schedules", headers=self.manager_headers)
        updated_doc = next(s for s in verify_res.json()["data"] if s["doctor"]["id"] == first_doc["doctor"]["id"])
        updated_day = updated_doc["days"][0]
        self.assertEqual(updated_day["start"], "10:00")
        self.assertEqual(updated_day["end"], "12:00")

    async def test_forgot_and_reset_password_flow(self):
        # Request forgot password
        forgot_res = await self.client.post("/auth/password/forgot", json={"phone": "07800000005"})
        self.assertEqual(forgot_res.status_code, 200)
        data = forgot_res.json()["data"]
        self.assertEqual(data["expires_in_minutes"], 10)
        # Should not leak internal codes to the user
        self.assertNotIn("dev_code", data)

        # Use the stored code to reset password
        from app.services.auth_service import _reset_codes
        code = _reset_codes["07800000005"]["code"]

        # Reset password
        reset_res = await self.client.post(
            "/auth/password/reset",
            json={
                "phone": "07800000005",
                "code": code,
                "new_password": "NewSecurePassword123!",
            },
        )
        self.assertEqual(reset_res.status_code, 200)

        # Verify login with new password
        login_res = await self.client.post(
            "/auth/login",
            json={
                "phone": "07800000005",
                "password": "NewSecurePassword123!",
            },
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("access_token", login_res.json()["data"])
