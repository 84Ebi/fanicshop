"""Catalog and cart service tests against real PostgreSQL."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, Product, ProductImage, User
from app.services.cart import (
    OutOfStock,
    TooMany,
    add_item,
    clear,
    get_or_create_cart,
    list_items,
    remove_item,
    set_qty,
    subtotal,
)
from app.services.catalog import first_image, list_categories, list_products, product_card


async def _seed(session: AsyncSession, *, stock: int = 5) -> tuple[Category, Product, User]:
    category = Category(slug="tea", title_fa="چای", sort_order=1)
    product = Product(
        category=category,
        title_fa="چای سبز",
        description_fa="دم کرده",
        price_rial=120_000,
        stock_qty=stock,
        reserved_qty=0,
    )
    image = ProductImage(product=product, telegram_file_id="AgAC_test", sort_order=0)
    user = User(telegram_id=7001, full_name="علی رضایی", status="verified", phone="9121234567")
    session.add_all([image, user])
    await session.flush()
    return category, product, user


async def test_catalog_queries(db_session: AsyncSession) -> None:
    category, product, _ = await _seed(db_session)
    assert await list_categories(db_session) == [category]
    assert await list_products(db_session, category.id) == [product]
    assert await first_image(db_session, product.id) == "AgAC_test"
    assert "۱۲٬۰۰۰ تومان" in product_card(product)


async def test_cart_add_update_remove(db_session: AsyncSession) -> None:
    _, product, user = await _seed(db_session)
    item = await add_item(db_session, user.id, product, 2)
    assert item.qty == 2 and item.price_at_add_rial == 120_000
    assert subtotal(await list_items(db_session, item.cart_id)) == 240_000

    cart = await get_or_create_cart(db_session, user.id)
    assert await get_or_create_cart(db_session, user.id) == cart  # idempotent
    assert (await set_qty(db_session, cart.id, item.id, 3)) is not None
    assert subtotal(await list_items(db_session, cart.id)) == 360_000

    assert await remove_item(db_session, cart.id, item.id)
    assert await list_items(db_session, cart.id) == []
    await clear(db_session, cart.id)


async def test_stock_and_qty_limits(db_session: AsyncSession) -> None:
    _, product, user = await _seed(db_session, stock=2)
    await add_item(db_session, user.id, product, 2)
    with pytest.raises(OutOfStock):
        await add_item(db_session, user.id, product, 1)
    with pytest.raises(TooMany):
        await add_item(db_session, user.id, product, 19)
    cart = await get_or_create_cart(db_session, user.id)
    item = (await list_items(db_session, cart.id))[0]
    with pytest.raises(OutOfStock):
        await set_qty(db_session, cart.id, item.id, 3)
    assert await set_qty(db_session, cart.id, item.id, 0) is None  # zero removes
