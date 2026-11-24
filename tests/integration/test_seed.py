"""M1: demo seed is idempotent and the ledger check runs clean."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, Product, Setting
from scripts.check_ledger import find_mismatches
from scripts.seed_demo import seed


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    cats1, prods1 = await seed(db_session)
    cats2, prods2 = await seed(db_session)
    assert (cats1, prods1) == (3, 6)
    assert (cats2, prods2) == (0, 0)
    assert await db_session.scalar(select(func.count()).select_from(Category)) == 3
    assert await db_session.scalar(select(func.count()).select_from(Product)) == 6
    assert await db_session.get(Setting, "shop_open") is not None


async def test_ledger_check_clean_on_empty_ledger(db_session: AsyncSession) -> None:
    assert await find_mismatches(db_session) == []
