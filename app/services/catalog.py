"""Catalog queries and product presentation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, Product, ProductImage
from app.i18n import money_rial


async def list_categories(session: AsyncSession) -> list[Category]:
    return list(
        await session.scalars(
            select(Category)
            .where(Category.is_active.is_(True))
            .order_by(Category.sort_order, Category.id)
        )
    )


async def get_category(session: AsyncSession, category_id: int) -> Category | None:
    return await session.get(Category, category_id)


async def list_products(session: AsyncSession, category_id: int) -> list[Product]:
    return list(
        await session.scalars(
            select(Product)
            .where(
                Product.category_id == category_id,
                Product.is_active.is_(True),
                Product.archived_at.is_(None),
            )
            .order_by(Product.sort_order, Product.id)
        )
    )


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    return await session.get(Product, product_id)


async def first_image(session: AsyncSession, product_id: int) -> str | None:
    return await session.scalar(
        select(ProductImage.telegram_file_id)
        .where(ProductImage.product_id == product_id)
        .order_by(ProductImage.sort_order, ProductImage.id)
        .limit(1)
    )


def available(product: Product) -> int:
    """Return currently sellable units (never negative)."""
    return max(0, product.stock_qty - product.reserved_qty)


async def create_category(session: AsyncSession, *, slug: str, title_fa: str) -> Category:
    category = Category(slug=slug.strip().lower(), title_fa=title_fa.strip())
    session.add(category)
    await session.flush()
    return category


async def create_product(
    session: AsyncSession,
    *,
    category_id: int,
    title_fa: str,
    description_fa: str | None,
    price_rial: int,
    stock_qty: int,
    photo_file_id: str | None = None,
) -> Product:
    product = Product(
        category_id=category_id,
        title_fa=title_fa.strip(),
        description_fa=(description_fa or "").strip() or None,
        price_rial=price_rial,
        stock_qty=stock_qty,
        reserved_qty=0,
    )
    session.add(product)
    await session.flush()
    if photo_file_id:
        session.add(ProductImage(product_id=product.id, telegram_file_id=photo_file_id))
        await session.flush()
    return product


async def set_price(session: AsyncSession, product: Product, price_rial: int) -> None:
    product.price_rial = price_rial
    await session.flush()


async def set_stock(session: AsyncSession, product: Product, stock_qty: int) -> None:
    if stock_qty < product.reserved_qty:
        raise ValueError("stock below reserved")
    product.stock_qty = stock_qty
    await session.flush()


async def archive_product(session: AsyncSession, product: Product) -> None:
    from datetime import UTC, datetime

    product.archived_at = datetime.now(UTC)
    product.is_active = False
    await session.flush()


def product_card(product: Product, *, description: str | None = None) -> str:
    from app.i18n import t

    text = description or product.description_fa or t("catalog.no_description")
    return t(
        "catalog.product_card",
        title=product.title_fa,
        description=text,
        price=money_rial(product.price_rial),
        stock=str(product.stock_qty - product.reserved_qty),
    )
