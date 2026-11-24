"""Test database bootstrap.

Integration tests run against a real PostgreSQL database (the money ledger
needs real isolation/partial indexes). The database is created if missing and
migrated with Alembic, exactly like production.

Override with TEST_DATABASE_URL when the local cluster differs.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
TEST_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://fanic@127.0.0.1:55432/fanic_test")


def _to_asyncpg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _ensure_database() -> None:
    dsn = _to_asyncpg_dsn(TEST_URL)
    base, dbname = dsn.rsplit("/", 1)
    conn = await asyncpg.connect(f"{base}/postgres")
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", dbname)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await conn.close()


def _alembic(*args: str) -> None:
    env = {**os.environ, "ALEMBIC_DATABASE_URL": TEST_URL}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    asyncio.run(_ensure_database())
    _alembic("upgrade", "head")


@pytest.fixture
async def engine(migrated_database: None) -> AsyncIterator[object]:
    eng = create_async_engine(TEST_URL, poolclass=None)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.rollback()

    # Clean slate for the next test (keep alembic_version).
    async with engine.begin() as conn:
        tables = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename <> 'alembic_version'"
            )
        )
        names = ", ".join(f'"{row[0]}"' for row in tables)
        if names:
            await conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
