import base64
import unittest
from decimal import Decimal
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from app.integrations.qi_gateway import QiGateway


class TestQiCardSandboxContract(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gateway = QiGateway(
            base_url="https://uat-sandbox-3ds-api.qi.iq/api/v1",
            username="paymentgatewaytest",
            password="WHaNFE5C3qlChqNbAzH4",
            terminal_id="237984",
        )

    def test_sandbox_initialization_and_auth_headers(self):
        """Verifies sandbox credentials, base URL, and Basic Auth header encoding."""
        self.assertEqual(self.gateway.base_url, "https://uat-sandbox-3ds-api.qi.iq/api/v1")
        self.assertEqual(self.gateway.terminal_id, "237984")

        headers = self.gateway._get_headers()
        self.assertIn("Authorization", headers)
        self.assertTrue(headers["Authorization"].startswith("Basic "))
        self.assertEqual(headers["X-Terminal-Id"], "237984")

        encoded_part = headers["Authorization"].split(" ")[1]
        decoded = base64.b64decode(encoded_part).decode("utf-8")
        self.assertEqual(decoded, "paymentgatewaytest:WHaNFE5C3qlChqNbAzH4")

    def test_canonical_signature_string_construction(self):
        """Verifies exact canonical string formatting with 3 decimal places."""
        canonical = self.gateway.build_canonical_signature_string(
            payment_id="PAY12345",
            amount=Decimal("15000.00"),
            currency="IQD",
            creation_date="2026-11-08T12:00:00Z",
            status="SUCCESS",
        )
        self.assertEqual(canonical, "PAY12345|15000.000|IQD|2026-11-08T12:00:00Z|SUCCESS")

    def test_rsa_sha256_webhook_signature_verification(self):
        """Generates a test RSA key pair and verifies valid and tampered webhook signatures."""
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()
        pub_pem = public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        canonical_data = self.gateway.build_canonical_signature_string(
            payment_id="PAY999",
            amount="25000",
            currency="IQD",
            creation_date="2026-11-08T15:30:00Z",
            status="SUCCESS",
        )
        sig_bytes = private_key.sign(
            canonical_data.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        valid_b64_sig = base64.b64encode(sig_bytes).decode("utf-8")

        # 1. Valid signature
        is_valid = self.gateway.verify_webhook_signature(
            signature_b64=valid_b64_sig,
            payment_id="PAY999",
            amount="25000",
            currency="IQD",
            creation_date="2026-11-08T15:30:00Z",
            status="SUCCESS",
            public_key_pem=pub_pem,
        )
        self.assertTrue(is_valid)

        # 2. Tampered amount in verification
        is_tampered = self.gateway.verify_webhook_signature(
            signature_b64=valid_b64_sig,
            payment_id="PAY999",
            amount="20000",  # Modified!
            currency="IQD",
            creation_date="2026-11-08T15:30:00Z",
            status="SUCCESS",
            public_key_pem=pub_pem,
        )
        self.assertFalse(is_tampered)

        # 3. Missing public key returns None (triggers authoritative fallback)
        res_none = self.gateway.verify_webhook_signature(
            signature_b64=valid_b64_sig,
            payment_id="PAY999",
            amount="25000",
            currency="IQD",
            creation_date="2026-11-08T15:30:00Z",
            status="SUCCESS",
            public_key_pem=None,
        )
        self.assertIsNone(res_none)
