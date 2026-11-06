from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings
from app.core.logging import logger
from app.database.base import Base

# Engine configuration
connect_args = {}
engine_kwargs = {
    "echo": settings.DB_ECHO,
    "future": True,
}

if "sqlite" in settings.DATABASE_URL:
    connect_args["check_same_thread"] = False
elif "postgresql" in settings.DATABASE_URL or "postgres" in settings.DATABASE_URL:
    connect_args["statement_cache_size"] = 0
    engine_kwargs["pool_size"] = 15
    engine_kwargs["max_overflow"] = 15
    engine_kwargs["pool_timeout"] = 30
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["pool_pre_ping"] = True

engine_kwargs["connect_args"] = connect_args
engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()
