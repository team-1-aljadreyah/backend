import base64
from decimal import Decimal
from typing import Dict, Any, Optional, Union
import httpx
from app.core.config import settings
from app.core.logging import logger

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
except ImportError:
    hashes = None
    padding = None
    load_pem_public_key = None


class QiGateway:
    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        terminal_id: Optional[str] = None,
        public_key_pem: Optional[str] = None,
    ):
        raw_url = base_url or settings.QI_BASE_URL or settings.QI_SANDBOX_BASE_URL
        self.base_url = raw_url.rstrip("/")
        self.username = username or settings.QI_USERNAME or "paymentgatewaytest"
        self.password = password or settings.QI_PASSWORD or "WHaNFE5C3qlChqNbAzH4"
        self.terminal_id = terminal_id or settings.QI_TERMINAL_ID or "237984"
        self.public_key_pem = public_key_pem or settings.QI_WEBHOOK_PUBLIC_KEY_PEM

    def _get_headers(self) -> Dict[str, str]:
        auth_bytes = f"{self.username}:{self.password}".encode("utf-8")
        auth_b64 = base64.b64encode(auth_bytes).decode("utf-8")
        return {
            "Authorization": f"Basic {auth_b64}",
            "X-Terminal-Id": str(self.terminal_id),
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Al-Rahma-Clinic/1.0",
        }

    async def create_payment(
        self,
        request_id: str,
        amount: Union[float, Decimal],
        currency: str = "IQD",
        finish_payment_url: str = "",
        notification_url: str = "",
        locale: str = "ar_IQ",
        app_channel: bool = False,
    ) -> Dict[str, Any]:
        """
        Initiates a payment session with the official QiCard Payment Gateway Sandbox.
        Endpoint: POST /payment
        """
        url = f"{self.base_url}/payment"
        numeric_amount = float(Decimal(str(amount)))
        payload = {
            "requestId": request_id,
            "amount": numeric_amount,
            "currency": currency,
            "locale": locale,
            "finishPaymentUrl": finish_payment_url,
            "notificationUrl": notification_url or "https://api.ama8.uk/payments/qi-webhook",
            "appChannel": app_channel,
        }
        headers = self._get_headers()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info(f"Qi payment created successfully: paymentId={data.get('paymentId')}")
                    return data
                else:
                    logger.error(f"Qi payment initiation failed [{resp.status_code}]: {resp.text}")
                    return {}
        except Exception as e:
            logger.error(f"Qi gateway connection error during create_payment: {e}")
            return {}

    async def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """
        Queries the official QiCard Payment Gateway Sandbox for transaction status.
        Endpoint: GET /payment/{payment_id}/status
        """
        url = f"{self.base_url}/payment/{payment_id}/status"
        headers = self._get_headers()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info(f"Qi payment status for {payment_id}: {data.get('status')}")
                    return data
                else:
                    logger.error(f"Qi payment status check failed [{resp.status_code}]: {resp.text}")
                    return {}
        except Exception as e:
            logger.error(f"Qi gateway connection error during get_payment_status: {e}")
            return {}

    async def refund_payment(
        self,
        payment_id: str,
        request_id: str,
        amount: Union[float, Decimal],
        message: str = "Clinic refund",
    ) -> Dict[str, Any]:
        """
        Issues a full or partial refund for a processed QiCard transaction.
        Endpoint: POST /payment/{payment_id}/refund
        """
        url = f"{self.base_url}/payment/{payment_id}/refund"
        headers = self._get_headers()
        numeric_amount = float(Decimal(str(amount)))
        payload = {
            "requestId": request_id,
            "amount": numeric_amount,
            "message": message,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info(f"Qi refund processed successfully: paymentId={payment_id}, status={data.get('status')}")
                    return data
                else:
                    logger.error(f"Qi refund failed [{resp.status_code}]: {resp.text}")
                    return {}
        except Exception as e:
            logger.error(f"Qi gateway connection error during refund_payment: {e}")
            return {}

    async def cancel_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Cancels a pending payment transaction on the gateway.
        Endpoint: POST /payment/{payment_id}/cancel
        """
        url = f"{self.base_url}/payment/{payment_id}/cancel"
        headers = self._get_headers()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info(f"Qi payment cancelled successfully: paymentId={payment_id}")
                    return data
                else:
                    logger.error(f"Qi payment cancel failed [{resp.status_code}]: {resp.text}")
                    return {}
        except Exception as e:
            logger.error(f"Qi gateway connection error during cancel_payment: {e}")
            return {}

    def build_canonical_signature_string(
        self,
        payment_id: str,
        amount: Union[float, Decimal, str],
        currency: str,
        creation_date: str,
        status: str,
    ) -> str:
        """
        Builds canonical signature string: paymentId|amount.000|currency|creationDate|status
        """
        d_amount = Decimal(str(amount))
        # Format with 3 decimal places as specified in Qi Card gateway contract
        formatted_amount = f"{d_amount:.3f}"
        return f"{payment_id}|{formatted_amount}|{currency}|{creation_date}|{status}"

    def verify_webhook_signature(
        self,
        signature_b64: str,
        payment_id: str,
        amount: Union[float, Decimal, str],
        currency: str,
        creation_date: str,
        status: str,
        public_key_pem: Optional[str] = None,
    ) -> Optional[bool]:
        """
        Verifies RSA-SHA256 signature from X-Signature header against the canonical string.
        Returns:
            True: Signature is verified and authentic.
            False: Signature is present but verification failed (tampering or invalid key).
            None: Public key is not configured; caller should fall back to authoritative server-to-server check.
        """
        pem = public_key_pem or self.public_key_pem
        if not pem or not pem.strip():
            logger.info("QiCard webhook: Public key not configured. Fallback to server-to-server verification.")
            return None

        if load_pem_public_key is None or padding is None or hashes is None:
            logger.warning("QiCard webhook: cryptography library not available for RSA verification.")
            return None

        try:
            canonical_data = self.build_canonical_signature_string(
                payment_id=payment_id,
                amount=amount,
                currency=currency,
                creation_date=creation_date,
                status=status,
            )
            raw_signature = base64.b64decode(signature_b64)
            pub_key = load_pem_public_key(pem.encode("utf-8"))
            pub_key.verify(  # type: ignore
                raw_signature,
                canonical_data.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            logger.info(f"QiCard webhook signature successfully verified for paymentId={payment_id}")
            return True
        except Exception as e:
            logger.warning(f"QiCard webhook signature verification failed for paymentId={payment_id}: {e}")
            return False


qi_gateway = QiGateway()
