"""Address, order creation, reservation and cancellation tests."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CartItem, Category, OrderItem, OrderStatusHistory, Product, User
from app.services.cart import add_item
from app.services.orders import (
    EmptyCart,
    NoAddress,
    StockChanged,
    cancel_order,
    create_address,
    create_order,
    format_order,
    list_addresses,
    list_orders,
)


async def _seed(session: AsyncSession, *, stock: int = 5) -> tuple[Product, User]:
    category = Category(slug="coffee", title_fa="قهوه")
    product = Product(
        category=category,
        title_fa="قهوه عربیکا",
        price_rial=200_000,
        stock_qty=stock,
        reserved_qty=0,
    )
    user = User(telegram_id=8001, full_name="علی رضایی", status="verified", phone="9121234567")
    session.add_all([product, user])
    await session.flush()
    return product, user


async def _address(session: AsyncSession, user: User):
    return await create_address(
        session,
        user.id,
        receiver_name="علی رضایی",
        receiver_phone="09121234567",
        province="تهران",
        city="تهران",
        address_line="خیابان آزادی، پلاک ۱۲",
        postal_code="1234567890",
    )


async def test_create_order_reserves_stock_and_snapshots(db_session: AsyncSession) -> None:
    product, user = await _seed(db_session)
    await add_item(db_session, user.id, product, 3)
    order = await create_order(
        db_session,
        user_id=user.id,
        contact_kind="phone",
        contact="9121234567",
        delivery_fee_rial=10_000,
    )

    assert order.public_code.startswith("F-")
    assert order.status == "awaiting_payment" and order.payment_state == "unpaid"
    assert order.subtotal_rial == 600_000 and order.total_rial == 610_000
    assert order.address_snapshot["contact_kind"] == "phone"
    assert order.address_snapshot["contact"] == "9121234567"
    assert (await db_session.get(Product, product.id)).reserved_qty == 3
    assert list(await db_session.scalars(select(CartItem))) == []

    items = (await db_session.scalars(select(OrderItem))).all()
    assert len(items) == 1 and items[0].title_snapshot == "قهوه عربیکا"
    history = (await db_session.scalars(select(OrderStatusHistory))).all()
    assert [h.to_status for h in history] == ["awaiting_payment"]

    items_text, address_text = await format_order(db_session, order)
    assert "قهوه عربیکا" in items_text
    assert "شماره تماس" in address_text and "۰۹۱۲" in address_text
    assert await list_orders(db_session, user.id) == [order]


async def test_create_order_guards(db_session: AsyncSession) -> None:
    product, user = await _seed(db_session)
    with pytest.raises(EmptyCart):
        await create_order(db_session, user_id=user.id, contact_kind="phone", contact="9121234567")

    await add_item(db_session, user.id, product, 2)
    with pytest.raises(NoAddress):
        await create_order(db_session, user_id=user.id, contact_kind="phone", contact="")

    product.reserved_qty = 4  # only 1 free left
    with pytest.raises(StockChanged):
        await create_order(
            db_session, user_id=user.id, contact_kind="phone", contact="9121234567"
        )


async def test_cancel_order_releases_stock(db_session: AsyncSession) -> None:
    product, user = await _seed(db_session)
    await add_item(db_session, user.id, product, 2)
    order = await create_order(
        db_session, user_id=user.id, contact_kind="phone", contact="9121234567"
    )

    assert await cancel_order(db_session, order, actor_telegram_id=9001)
    assert order.status == "cancelled" and order.cancelled_at is not None
    assert (await db_session.get(Product, product.id)).reserved_qty == 0
    assert not await cancel_order(db_session, order)  # idempotent-ish guard
    history = (await db_session.scalars(select(OrderStatusHistory))).all()
    assert [h.to_status for h in history] == ["awaiting_payment", "cancelled"]


async def test_address_default_and_validation(db_session: AsyncSession) -> None:
    _, user = await _seed(db_session)
    first = await _address(db_session, user)
    assert first.is_default
    with pytest.raises(ValueError):
        await create_address(
            db_session,
            user.id,
            receiver_name="علی رضایی",
            receiver_phone="123",
            province="تهران",
            city="تهران",
            address_line="خیابان آزادی، پلاک ۱۲",
        )
    assert len(await list_addresses(db_session, user.id)) == 1
