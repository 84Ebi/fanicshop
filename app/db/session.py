"""Async engine / session factory.

SQLite is NOT used: this is a money ledger that needs real transaction
isolation (SELECT … FOR UPDATE), partial unique indexes, and concurrent
writers — PostgreSQL only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings


def create_engine(settings: Settings, **kwargs: Any) -> AsyncEngine:
    return create_async_engine(settings.database_url, pool_pre_ping=True, **kwargs)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a session and always commit/close (errors roll back then close)."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
