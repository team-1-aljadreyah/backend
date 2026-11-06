import base64
import json
from typing import Dict, Any, Optional
import httpx
from app.core.logging import logger

QI_SANDBOX_BASE_URL = "https://uat-sandbox-3ds-api.qi.iq/api/v1"
QI_SANDBOX_USERNAME = "paymentgatewaytest"
QI_SANDBOX_PASSWORD = "WHaNFE5C3qlChqNbAzH4"
QI_SANDBOX_TERMINAL_ID = "237984"


class QiGateway:
    def __init__(
        self,
        base_url: str = QI_SANDBOX_BASE_URL,
        username: str = QI_SANDBOX_USERNAME,
        password: str = QI_SANDBOX_PASSWORD,
        terminal_id: str = QI_SANDBOX_TERMINAL_ID,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.terminal_id = terminal_id

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
        amount: float,
        currency: str = "IQD",
        finish_payment_url: str = "",
        notification_url: str = "",
        locale: str = "ar_IQ",
    ) -> Dict[str, Any]:
        """Initiates a payment session with the QiCard Payment Gateway Sandbox."""
        url = f"{self.base_url}/payment"
        payload = {
            "requestId": request_id,
            "amount": float(amount),
            "currency": currency,
            "locale": locale,
            "finishPaymentUrl": finish_payment_url,
            "notificationUrl": notification_url or "https://api.ama8.uk/payments/qi-webhook",
            "appChannel": False,
        }
        headers = self._get_headers()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
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
        """Queries the QiCard Payment Gateway Sandbox for transaction status."""
        url = f"{self.base_url}/payment/{payment_id}/status"
        headers = self._get_headers()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
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


qi_gateway = QiGateway()
