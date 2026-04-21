"""FastAPI dependency injection providers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from tokenlens.core.config import settings
from tokenlens.core.database import get_session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session for use as a FastAPI Depends."""
    async with get_session() as session:
        yield session


def get_config():
    """Return dynaconf settings object."""
    return settings
