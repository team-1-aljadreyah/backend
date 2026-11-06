import unittest
from tests.conftest import get_test_client, auth_headers


class TestPharmacyAndInventory(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        self.pharmacy_headers = auth_headers(user_id=4, role="pharmacy")
        self.doctor_headers = auth_headers(user_id=2, role="doctor")
        self.reception_headers = auth_headers(user_id=1, role="reception")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_stock_listing_and_catalog(self):
        # Pharmacy stock list
        res = await self.client.get("/pharmacy/stock", headers=self.pharmacy_headers)
        self.assertEqual(res.status_code, 200)
        items = res.json()["data"]
        self.assertTrue(len(items) > 0)
        self.assertIn("level", items[0])
        self.assertIn("expiry", items[0])

        # Doctor catalog
        c_res = await self.client.get("/pharmacy/catalog", headers=self.doctor_headers)
        self.assertEqual(c_res.status_code, 200)
        catalog = c_res.json()["data"]
        self.assertTrue(len(catalog) > 0)
        self.assertIn("availability", catalog[0])

    async def test_over_counter_sale(self):
        # Sell 2 Paracetamol 500mg (id = 60, unit_price = 250, available >= 2)
        payload = {
            "customer": "Walkin Customer",
            "lines": [{"stock_id": 60, "quantity": 2}],
            "idempotency_key": "otc-test-key-001",
        }
        res = await self.client.post("/pharmacy/sales", json=payload, headers=self.pharmacy_headers)
        self.assertEqual(res.status_code, 200)
        sale = res.json()["data"]
        self.assertEqual(sale["total"], 500.0)

        # Verify stock moves log
        log_res = await self.client.get("/pharmacy/stock/log?limit=5", headers=self.pharmacy_headers)
        self.assertEqual(log_res.status_code, 200)
        moves = log_res.json()["data"]
        self.assertTrue(any(m["kind"] == "sale" and m["stock_id"] == 60 for m in moves))

    async def test_stock_receive_delivery(self):
        rec_payload = {"quantity": 50, "expires_on": "2027-12-31"}
        res = await self.client.post("/pharmacy/stock/60/receive", json=rec_payload, headers=self.pharmacy_headers)
        self.assertEqual(res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
