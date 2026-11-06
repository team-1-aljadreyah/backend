from typing import Dict, Any
from app.core.config import settings
from app.core.logging import logger


class PaymentGateway:
    def __init__(self):
        self.mode = settings.PAYMENT_PROVIDER_MODE

    async def process_online_payment(
        self,
        amount: float,
        currency: str,
        idempotency_key: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        logger.info(f"Processing {self.mode} online payment of {amount} {currency} [key: {idempotency_key}]")
        # In mock or production gateway, return structured payment transaction data
        return {
            "status": "success",
            "transaction_id": f"txn_{idempotency_key[:16]}",
            "amount": amount,
            "currency": currency,
        }

    async def process_refund(
        self,
        payment_id: int,
        amount: float,
        currency: str,
        reason: str,
    ) -> Dict[str, Any]:
        logger.info(f"Processing refund for payment {payment_id}: {amount} {currency} ({reason})")
        return {
            "status": "refunded",
            "refund_id": f"ref_{payment_id}",
            "amount": amount,
        }


payment_gateway = PaymentGateway()
