from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_SETTINGS = get_settings()
_DATABASE_URL = (
    f"postgresql+asyncpg://{_SETTINGS.postgres_user}:{_SETTINGS.postgres_password}"
    f"@{_SETTINGS.postgres_host}:{_SETTINGS.postgres_port}/{_SETTINGS.postgres_db}"
)

engine: AsyncEngine = create_async_engine(_DATABASE_URL, echo=False, future=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Provide an async SQLAlchemy session for dependency injection."""

    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
