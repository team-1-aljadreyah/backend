import asyncio
import os
import sys
from typing import Dict, Any
import httpx
from httpx import ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Point to clean test database
import atexit

PID = os.getpid()
TEST_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), f"test_suite_{PID}.db"))
if os.path.exists(TEST_DB_PATH):
    try:
        os.remove(TEST_DB_PATH)
    except Exception:
        pass

def cleanup():
    try:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
    except Exception:
        pass

atexit.register(cleanup)

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["APP_ENV"] = "testing"

from app.core.config import settings
settings.DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

from app.database.connection import engine, AsyncSessionLocal
from app.database.base import Base
from app.main import app, init_default_data
from app.core.security import create_access_token


async def get_test_client() -> httpx.AsyncClient:
    await init_default_data()
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def auth_headers(user_id: int, role: str) -> Dict[str, str]:
    token = create_access_token({"sub": str(user_id), "role": role})
    return {"Authorization": f"Bearer {token}"}
