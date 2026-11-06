import unittest
from datetime import date
from tests.conftest import get_test_client, auth_headers


class TestFinanceAndAccounting(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        self.reception_headers = auth_headers(user_id=1, role="reception")
        self.accountant_headers = auth_headers(user_id=8, role="accountant")
        self.manager_headers = auth_headers(user_id=6, role="manager")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_invoices_and_cash_payment(self):
        # 1. Create walk-in to get an appointment with fee
        w_res = await self.client.post(
            "/walk-ins",
            json={"name": "Billing Patient", "phone": "07700112233", "doctor_id": 1, "emergency": False},
            headers=self.reception_headers,
        )
        self.assertEqual(w_res.status_code, 200)

        # 2. View today's invoices
        inv_res = await self.client.get("/invoices/today", headers=self.reception_headers)
        self.assertEqual(inv_res.status_code, 200)
        invoices = inv_res.json()["data"]
        inv = next(i for i in invoices if i["patient_name"] == "Billing Patient")
        appt_id = inv["appointment_id"]
        rem_iqd = inv["money"]["balance"]["IQD"]
        self.assertEqual(rem_iqd, 25000.0)

        # 3. Pay cash
        pay_payload = {
            "amount": 25000.0,
            "currency": "IQD",
            "idempotency_key": f"pay-cash-{appt_id}",
        }
        p_res = await self.client.post(f"/appointments/{appt_id}/pay-cash", json=pay_payload, headers=self.reception_headers)
        self.assertEqual(p_res.status_code, 200)

        # 4. Prevent overpayment
        bad_pay = {
            "amount": 5000.0,
            "currency": "IQD",
            "idempotency_key": f"pay-over-{appt_id}",
        }
        over_res = await self.client.post(f"/appointments/{appt_id}/pay-cash", json=bad_pay, headers=self.reception_headers)
        self.assertEqual(over_res.status_code, 409)

    async def test_reception_shift_and_closing(self):
        # View shift summary
        shift_res = await self.client.get("/cash/shift", headers=self.reception_headers)
        self.assertEqual(shift_res.status_code, 200)
        shift = shift_res.json()["data"]
        self.assertIn("expected", shift)

        # Close shift
        close_payload = {
            "counted": {"IQD": shift["expected"]["IQD"], "USD": 0.0},
            "note": "Shift closed smoothly",
        }
        close_res = await self.client.post("/cash/closings", json=close_payload, headers=self.reception_headers)
        self.assertEqual(close_res.status_code, 200)
        closing = close_res.json()["data"]
        self.assertEqual(closing["difference"]["IQD"], 0.0)

    async def test_expenses_management_and_voiding(self):
        today_str = str(date.today())
        exp_payload = {
            "date": today_str,
            "category": "supplies",
            "amount": 75000.0,
            "currency": "IQD",
            "note": "Medical gloves and masks",
        }
        add_res = await self.client.post("/expenses", json=exp_payload, headers=self.accountant_headers)
        self.assertEqual(add_res.status_code, 200)
        exp_id = add_res.json()["data"]["id"]

        # Void expense
        void_res = await self.client.post(f"/expenses/{exp_id}/void", json={"reason": "Incorrect quantity billed"}, headers=self.accountant_headers)
        self.assertEqual(void_res.status_code, 200)
        self.assertIsNotNone(void_res.json()["data"]["voided"])

    async def test_ledger_and_payment_reversal(self):
        ledger_res = await self.client.get("/ledger", headers=self.accountant_headers)
        self.assertEqual(ledger_res.status_code, 200)
        data = ledger_res.json()["data"]
        entries = data["items"] if isinstance(data, dict) and "items" in data else data

        # Find a reversible payment
        rev_target = next((e for e in entries if e["reversible"]), None)
        if rev_target:
            rev_res = await self.client.post(f"/payments/{rev_target['id']}/reverse", json={"reason": "Audit adjustment error"}, headers=self.accountant_headers)
            self.assertEqual(rev_res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
