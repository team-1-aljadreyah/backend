from typing import List, Optional, Union, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Al-Jadreyah Clinic Management System"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_TIMEZONE: str = "Asia/Baghdad"
    SECRET_KEY: str = "default-secret-key-change-in-production-min-32-chars-long"

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./clinic.db",
        description="Async PostgreSQL connection string (or SQLite for testing/local execution)",
    )
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Supabase Integration
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_PUBLISHABLE_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_SECRET_KEY: Optional[str] = None
    SUPABASE_JWKS_URL: Optional[str] = None
    SUPABASE_STORAGE_BUCKET: str = "lab-results"

    @property
    def anon_key(self) -> str:
        return self.SUPABASE_PUBLISHABLE_KEY or self.SUPABASE_ANON_KEY or ""

    @property
    def service_role_key(self) -> str:
        return self.SUPABASE_SECRET_KEY or self.SUPABASE_SERVICE_ROLE_KEY or ""

    # Security & Tokens
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    # CORS
    FRONTEND_ORIGINS: Union[str, List[str]] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    # Logging
    LOG_LEVEL: str = "INFO"

    # Payment Gateway
    PAYMENT_PROVIDER_MODE: str = "mock"
    PAYMENT_GATEWAY_API_KEY: Optional[str] = None

    @field_validator("FRONTEND_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            if v.strip() == "*":
                return ["*"]
            if not v.startswith("["):
                return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        return []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
