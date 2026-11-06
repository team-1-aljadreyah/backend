from typing import Any, Dict, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.core.security import normalize_phone_e164


class SupabaseAuthClient:
    def __init__(self):
        self.enabled = bool(settings.SUPABASE_URL and settings.anon_key)
        self.base_url = settings.SUPABASE_URL.rstrip("/") if settings.SUPABASE_URL else ""
        self.anon_key = settings.anon_key
        self.service_key = settings.service_role_key

    def _headers(self, service: bool = False) -> Dict[str, str]:
        key = self.service_key if service and self.service_key else self.anon_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    async def sign_up_phone(self, phone: str, password: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        url = f"{self.base_url}/auth/v1/signup"
        phone_e164 = normalize_phone_e164(phone)
        payload = {
            "phone": phone_e164,
            "password": password,
            "data": metadata or {},
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload, headers=self._headers())
                if res.status_code in (200, 201):
                    return res.json()
                logger.warning(f"Supabase sign_up_phone returned {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Supabase sign_up_phone failed: {e}")
        return None

    async def sign_in_phone(self, phone: str, password: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        url = f"{self.base_url}/auth/v1/token?grant_type=password"
        phone_e164 = normalize_phone_e164(phone)
        payload = {
            "phone": phone_e164,
            "password": password,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload, headers=self._headers())
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"Supabase sign_in_phone returned {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Supabase sign_in_phone failed: {e}")
        return None

    async def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        url = f"{self.base_url}/auth/v1/token?grant_type=refresh_token"
        payload = {"refresh_token": refresh_token}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload, headers=self._headers())
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"Supabase refresh_token returned {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Supabase refresh_token failed: {e}")
        return None


supabase_auth = SupabaseAuthClient()
