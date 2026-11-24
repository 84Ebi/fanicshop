"""Seed a demo catalog + default settings.

Idempotent: safe to run on every deploy. Uses neutral product wording — the
shop's real catalog is managed from the admin panel and lives in the DB only.

Usage:
    python -m scripts.seed_demo [--database-url postgresql+asyncpg://...]
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Category, Product, Setting

DEMO_CATEGORIES: list[dict] = [
    {"slug": "demo-1", "title_fa": "دسته نمونه ۱", "sort_order": 1},
    {"slug": "demo-2", "title_fa": "دسته نمونه ۲", "sort_order": 2},
    {"slug": "demo-3", "title_fa": "دسته نمونه ۳", "sort_order": 3},
]

DEMO_PRODUCTS: list[dict] = [
    {"slug": "demo-1", "title_fa": "محصول نمونه ۱", "price_rial": 250_000, "stock_qty": 10},
    {"slug": "demo-1", "title_fa": "محصول نمونه ۲", "price_rial": 480_000, "stock_qty": 5},
    {"slug": "demo-2", "title_fa": "محصول نمونه ۳", "price_rial": 1_200_000, "stock_qty": 3},
    {"slug": "demo-2", "title_fa": "محصول نمونه ۴", "price_rial": 890_000, "stock_qty": 0},
    {"slug": "demo-3", "title_fa": "محصول نمونه ۵", "price_rial": 75_000, "stock_qty": 50},
    {"slug": "demo-3", "title_fa": "محصول نمونه ۶", "price_rial": 320_000, "stock_qty": 12},
]

DEFAULT_SETTINGS: dict[str, object] = {
    "shop_open": True,
    "payment_window_minutes": 15,
    "suffix_min_toman": 1,
    "suffix_max_toman": 999,
    "free_delivery_threshold_rial": 5_000_000,
    "delivery_fee_rial": 80_000,
}


async def seed(session: AsyncSession) -> tuple[int, int]:
    categories = 0
    products = 0

    by_slug: dict[str, Category] = {}
    for data in DEMO_CATEGORIES:
        existing = await session.scalar(select(Category).where(Category.slug == data["slug"]))
        if existing is None:
            existing = Category(**data)
            session.add(existing)
            await session.flush()
            categories += 1
        by_slug[data["slug"]] = existing

    for data in DEMO_PRODUCTS:
        exists = await session.scalar(
            select(Product.id).where(
                Product.title_fa == data["title_fa"],
                Product.category_id == by_slug[data["slug"]].id,
            )
        )
        if exists is None:
            session.add(
                Product(
                    category_id=by_slug[data["slug"]].id,
                    title_fa=data["title_fa"],
                    price_rial=data["price_rial"],
                    stock_qty=data["stock_qty"],
                    description_fa="توضیحات نمونه — از پنل مدیریت قابل ویرایش است.",
                )
            )
            products += 1

    for key, value in DEFAULT_SETTINGS.items():
        if await session.get(Setting, key) is None:
            session.add(Setting(key=key, value=value))

    await session.commit()
    return categories, products


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    url = args.database_url or get_settings().database_url
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as session:
            cats, prods = await seed(session)
        print(f"seed ok: {cats} categories, {prods} products added")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
