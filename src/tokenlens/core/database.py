"""Async SQLAlchemy engine, session factory, and lifecycle functions."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tokenlens.core.models import Base

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# Default DB path: ~/.tokenlens/tokenlens.db
_DEFAULT_DB_URL: str | None = None


def _default_db_url() -> str:
    from tokenlens.core.config import get_db_path

    return f"sqlite+aiosqlite:///{get_db_path()}"


async def init_engine(db_url: str | None = None) -> AsyncEngine:
    """Initialize the async SQLAlchemy engine. Idempotent."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        return _engine

    if db_url is None:
        db_url = _default_db_url()

    _engine = create_async_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    # Enable WAL mode for concurrent read/write (daemon writes, API reads)
    # and create tables if they don't exist
    async with _engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(Base.metadata.create_all)

    return _engine


async def get_engine() -> AsyncEngine:
    """Return existing engine or initialize a new one."""
    if _engine is None:
        await init_engine()
    assert _engine is not None
    return _engine


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager yielding a session with commit/rollback."""
    if _session_factory is None:
        await init_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_engine() -> None:
    """Dispose engine and reset globals."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
