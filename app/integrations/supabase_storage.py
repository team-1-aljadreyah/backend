import os
import base64
from typing import Optional, Tuple
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import UnprocessableEntityException

ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg"}
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2MB


class SupabaseStorageClient:
    def __init__(self):
        self.enabled = bool(settings.SUPABASE_URL and settings.service_role_key)
        self.base_url = settings.SUPABASE_URL.rstrip("/") if settings.SUPABASE_URL else ""
        self.service_key = settings.service_role_key
        self.bucket = settings.SUPABASE_STORAGE_BUCKET
        self.local_dir = os.path.join(os.getcwd(), "uploads", self.bucket)
        os.makedirs(self.local_dir, exist_ok=True)

    def _headers(self) -> dict:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
        }

    def validate_file(self, content_type: str, file_size: int):
        if content_type not in ALLOWED_MIME_TYPES:
            raise UnprocessableEntityException(
                message=f"File type '{content_type}' is not allowed. Supported: {list(ALLOWED_MIME_TYPES)}",
                code="validation.fileType",
            )
        if file_size > MAX_FILE_BYTES:
            raise UnprocessableEntityException(
                message=f"File exceeds maximum allowed size of {MAX_FILE_BYTES} bytes",
                code="validation.fileSize",
            )

    async def upload_file(self, file_name: str, content: bytes, content_type: str) -> str:
        self.validate_file(content_type, len(content))

        if self.enabled:
            url = f"{self.base_url}/storage/v1/object/{self.bucket}/{file_name}"
            headers = self._headers()
            headers["Content-Type"] = content_type
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(url, content=content, headers=headers)
                    if res.status_code in (200, 201):
                        return file_name
                    logger.warning(f"Supabase storage upload returned {res.status_code}: {res.text}")
            except Exception as e:
                logger.error(f"Supabase storage upload error: {e}")

        # Local filesystem fallback
        local_path = os.path.join(self.local_dir, file_name)
        with open(local_path, "wb") as f:
            f.write(content)

        # Return data URL or relative path
        b64_content = base64.b64encode(content).decode("utf-8")
        return f"data:{content_type};base64,{b64_content}"

    async def create_signed_url(self, file_name: str, expires_in: int = 315360000) -> Optional[str]:
        if not self.enabled:
            return None
        url = f"{self.base_url}/storage/v1/object/sign/{self.bucket}/{file_name}"
        headers = self._headers()
        headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json={"expiresIn": expires_in})
                if res.status_code == 200:
                    signed_path = res.json().get("signedURL")
                    return f"{self.base_url}/storage/v1{signed_path}"
                logger.warning(f"Supabase create signed URL returned {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Supabase create signed URL error: {e}")
        return None

    async def get_file_content(self, file_name: str) -> Optional[Tuple[bytes, str]]:
        if self.enabled:
            url = f"{self.base_url}/storage/v1/object/authenticated/{self.bucket}/{file_name}"
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.get(url, headers=self._headers())
                    if res.status_code == 200:
                        content_type = res.headers.get("content-type", "application/octet-stream")
                        return res.content, content_type
            except Exception as e:
                logger.error(f"Supabase storage retrieve error: {e}")

        local_path = os.path.join(self.local_dir, file_name)
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                content = f.read()
            ext = os.path.splitext(file_name)[1].lower()
            ct = "application/pdf" if ext == ".pdf" else "image/png" if ext == ".png" else "image/jpeg"
            return content, ct
        return None


supabase_storage = SupabaseStorageClient()
