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
