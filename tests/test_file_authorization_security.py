import unittest
from app.core.security import create_file_download_token, verify_file_download_token
from tests.conftest import get_test_client, auth_headers


class TestFileAuthorizationSecurity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()
        self.patient_headers = auth_headers(1, "patient")
        self.reception_headers = auth_headers(2, "reception")

    def test_signed_token_creation_and_cryptographic_verification(self):
        """Verifies HMAC/JWT token signing for safe image loading in standard <img> tags."""
        token = create_file_download_token(
            filename="test_image.jpg",
            bucket="welfare",
            user_id=1,
            role="patient",
            expires_in_seconds=60,
        )
        self.assertTrue(len(token) > 20)

        # 1. Valid token verification
        info = verify_file_download_token(token, filename="test_image.jpg", bucket="welfare")
        self.assertIsNotNone(info)
        self.assertEqual(info["user_id"], 1)

        # 2. Bucket mismatch
        mismatched_bucket = verify_file_download_token(token, filename="test_image.jpg", bucket="lab-results")
        self.assertIsNone(mismatched_bucket)

        # 3. Filename mismatch
        mismatched_filename = verify_file_download_token(token, filename="other_image.jpg", bucket="welfare")
        self.assertIsNone(mismatched_filename)

        # 4. Tampered token string
        tampered = verify_file_download_token(token + "tampered", filename="test_image.jpg", bucket="welfare")
        self.assertIsNone(tampered)

    async def test_unauthenticated_file_download_rejection(self):
        """Verifies that downloading a file without a token or Bearer header returns 401."""
        res = await self.client.get("/storage/v1/object/authenticated/welfare/sample.jpg")
        self.assertEqual(res.status_code, 401)

        res2 = await self.client.get("/files/welfare/sample.jpg")
        self.assertEqual(res2.status_code, 401)

    async def test_path_traversal_prevention(self):
        """Verifies that path traversal attempts are safely rejected with 400 or 404 (not found / invalid route)."""
        token = create_file_download_token(
            filename="sample.jpg",
            bucket="welfare",
            user_id=1,
            role="patient",
        )
        res = await self.client.get(f"/storage/v1/object/authenticated/welfare/..%2F..%2Fetc%2Fpasswd?token={token}")
        self.assertIn(res.status_code, (400, 404))

        res2 = await self.client.get(f"/storage/v1/object/authenticated/welfare/subdir/evil.jpg?token={token}")
        self.assertIn(res2.status_code, (400, 404))
