from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings
from app.core.logging import logger
router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException

from app.database.connection import engine


@router.get("/health/ready")
async def readiness_check():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        return {
            "status": "ready",
            "database": "connected"
        }

except SQLAlchemyError as exc:

    logger.error(
        "Readiness check failed: database connection error (%s)",
        type(exc).__name__
    )

    raise HTTPException(
        status_code=503,
        detail="Database is unavailable"
    ) from exc
