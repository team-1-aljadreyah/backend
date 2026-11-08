import os
import base64
from pathlib import Path
from typing import Optional, Tuple
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import UnprocessableEntityException

ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/jpg"}
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2MB


class SupabaseStorageClient:
    def __init__(self):
        self.enabled = bool(settings.SUPABASE_URL and settings.service_role_key)
        self.base_url = settings.SUPABASE_URL.rstrip("/") if settings.SUPABASE_URL else ""
        self.service_key = settings.service_role_key
        self.bucket = settings.SUPABASE_STORAGE_BUCKET
        # Use backend root relative directory for uploads
        backend_root = Path(__file__).resolve().parent.parent.parent
        self.upload_root = backend_root / "uploads"
        self.local_dir = self.upload_root / self.bucket
        os.makedirs(self.local_dir, exist_ok=True)

    def _headers(self) -> dict:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
        }

    def validate_file(self, content_type: str, content: bytes, file_name: str):
        safe_name = os.path.basename(file_name)
        if not safe_name or safe_name != file_name or ".." in file_name or "/" in file_name or "\\" in file_name:
            raise UnprocessableEntityException(
                message="Invalid file name: path traversal characters detected",
                code="validation.invalidFileName",
            )

        if content_type not in ALLOWED_MIME_TYPES:
            raise UnprocessableEntityException(
                message=f"File type '{content_type}' is not allowed. Supported: {list(ALLOWED_MIME_TYPES)}",
                code="validation.fileType",
            )

        if len(content) > MAX_FILE_BYTES:
            raise UnprocessableEntityException(
                message=f"File exceeds maximum allowed size of {MAX_FILE_BYTES} bytes",
                code="validation.fileSize",
            )

        # Magic bytes verification
        if content_type == "application/pdf":
            if not content.startswith(b"%PDF"):
                raise UnprocessableEntityException(
                    message="Corrupted or invalid PDF file header",
                    code="validation.fileHeader",
                )
        elif content_type == "image/png":
            if not content.startswith(b"\x89PNG"):
                raise UnprocessableEntityException(
                    message="Corrupted or invalid PNG file header",
                    code="validation.fileHeader",
                )
        elif content_type in ("image/jpeg", "image/jpg"):
            if not content.startswith(b"\xff\xd8\xff"):
                raise UnprocessableEntityException(
                    message="Corrupted or invalid JPEG file header",
                    code="validation.fileHeader",
                )

    async def upload_file(
        self,
        file_name: str,
        content: bytes,
        content_type: str,
        bucket: Optional[str] = None,
    ) -> str:
        self.validate_file(content_type, content, file_name)
        target_bucket = bucket or self.bucket

        if self.enabled:
            url = f"{self.base_url}/storage/v1/object/{target_bucket}/{file_name}"
            headers = self._headers()
            headers["Content-Type"] = content_type
            headers["x-upsert"] = "true"
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(url, content=content, headers=headers)
                    if res.status_code in (200, 201):
                        return file_name
                    logger.warning(f"Supabase storage upload returned {res.status_code}: {res.text}")
            except Exception as e:
                logger.error(f"Supabase storage upload error: {e}")

        # Local filesystem fallback
        target_dir = self.upload_root / target_bucket
        os.makedirs(target_dir, exist_ok=True)
        local_path = target_dir / file_name
        with open(local_path, "wb") as f:
            f.write(content)

        return file_name

    async def create_signed_url(
        self,
        file_name: str,
        expires_in: Optional[int] = None,
        bucket: Optional[str] = None,
    ) -> Optional[str]:
        if not self.enabled:
            return None
        target_bucket = bucket or self.bucket
        ttl = expires_in if expires_in is not None else settings.STORAGE_SIGNED_URL_EXPIRE_SECONDS
        url = f"{self.base_url}/storage/v1/object/sign/{target_bucket}/{file_name}"
        headers = self._headers()
        headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json={"expiresIn": ttl})
                if res.status_code == 200:
                    signed_path = res.json().get("signedURL")
                    return f"{self.base_url}/storage/v1{signed_path}"
                logger.warning(f"Supabase create signed URL returned {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Supabase create signed URL error: {e}")
        return None

    async def get_file_content(
        self,
        file_name: str,
        bucket: Optional[str] = None,
    ) -> Optional[Tuple[bytes, str]]:
        target_bucket = bucket or self.bucket
        safe_name = os.path.basename(file_name)
        if not safe_name or safe_name != file_name or ".." in file_name or "/" in file_name or "\\" in file_name:
            return None

        if self.enabled:
            # Check authenticated endpoint in Supabase
            url = f"{self.base_url}/storage/v1/object/authenticated/{target_bucket}/{safe_name}"
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.get(url, headers=self._headers())
                    if res.status_code == 200:
                        content_type = res.headers.get("content-type", "application/octet-stream")
                        return res.content, content_type
            except Exception as e:
                logger.error(f"Supabase storage retrieve error: {e}")

        # Local directory check
        possible_dirs = [
            self.upload_root / target_bucket,
            self.upload_root / "welfare",
            self.upload_root / "lab-results",
            self.upload_root,
            Path(os.getcwd()) / "uploads" / target_bucket,
            Path(os.getcwd()) / "uploads" / "welfare",
            Path(os.getcwd()) / "uploads" / "lab-results",
            Path(os.getcwd()) / "uploads",
        ]

        for p_dir in possible_dirs:
            local_path = (p_dir / safe_name).resolve()
            if local_path.is_file():
                with open(local_path, "rb") as f:
                    content = f.read()
                ext = os.path.splitext(safe_name)[1].lower()
                ct = "application/pdf" if ext == ".pdf" else "image/png" if ext == ".png" else "image/jpeg"
                return content, ct

        return None


supabase_storage = SupabaseStorageClient()
