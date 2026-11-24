"""M4: addresses + order creation with stock reservation and status history."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Address, Category, OrderItem, OrderStatusHistory, Product, User
from app.services.cart import add_item, get_or_create_cart, list_items
from app.services.catalog import available
from app.services.orders import (
    EmptyCart,
    NoAddress,
    StockChanged,
    cancel_order,
    create_address,
    create_order,
    get_order,
    list_addresses,
    list_orders,
)


async def _seed(session: AsyncSession, *, stock: int = 10) -> tuple[User, Product]:
    category = Category(slug="tea", title_fa="چای", sort_order=1)
    product = Product(
        category=category,
        title_fa="چای سبز",
        description_fa="دم کرده",
        price_rial=120_000,
        stock_qty=stock,
        reserved_qty=0,
    )
    user = User(telegram_id=7101, full_name="علی رضایی", status="verified", phone="9121234567")
    session.add_all([user, product])
    await session.flush()
    return user, product


async def _address(session: AsyncSession, user_id: int) -> Address:
    return await create_address(
        session,
        user_id,
        receiver_name="علی رضایی",
        receiver_phone="09121234567",
        province="تهران",
        city="تهران",
        address_line="خیابان آزادی، پلاک ۱۲",
        postal_code="1234567890",
        note="تماس قبل از تحویل",
    )


async def test_address_lifecycle(db_session: AsyncSession) -> None:
    user, _ = await _seed(db_session)
    first = await _address(db_session, user.id)
    assert first.is_default is True

    second = await create_address(
        db_session,
        user.id,
        receiver_name="مریم احمدی",
        receiver_phone="09351234567",
        province="اصفهان",
        city="اصفهان",
        address_line="خیابان چهارباغ، پلاک ۸۸",
    )
    assert second.is_default is False

    listed = await list_addresses(db_session, user.id)
    assert [a.id for a in listed] == [first.id, second.id]  # default first

    with pytest.raises(ValueError):
        await create_address(
            db_session, user.id, receiver_name="", receiver_phone="09121234567",
            province="x", city="y", address_line="short",
        )


async def test_create_order_reserves_and_snapshots(db_session: AsyncSession) -> None:
    user, product = await _seed(db_session)
    await add_item(db_session, user.id, product, 2)
    address = await _address(db_session, user.id)

    order = await create_order(
        db_session,
        user_id=user.id,
        address=address,
        delivery_note="تماس قبل از تحویل",
        delivery_fee_rial=5_000,
        actor_telegram_id=user.telegram_id,
    )
    await db_session.flush()

    assert order.status == "awaiting_payment"
    assert order.payment_state == "unpaid"
    assert order.public_code.startswith("F-")
    assert order.subtotal_rial == 240_000
    assert order.delivery_fee_rial == 5_000
    assert order.total_rial == 245_000
    assert order.wallet_paid_rial == 0 and order.card_paid_rial == 0
    assert order.address_snapshot["receiver_name"] == "علی رضایی"
    assert order.delivery_note == "تماس قبل از تحویل"

    # stock reservation
    assert product.reserved_qty == 2
    assert available(product) == 8

    # cart is cleared
    cart = await get_or_create_cart(db_session, user.id)
    assert await list_items(db_session, cart.id) == []

    # order items snapshot
    order_items = (
        await db_session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))
    ).all()
    assert len(order_items) == 1
    assert order_items[0].title_snapshot == "چای سبز"
    assert order_items[0].unit_price_rial == 120_000
    assert order_items[0].qty == 2
    assert order_items[0].line_total_rial == 240_000

    # history
    events = (
        await db_session.scalars(
            select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id)
        )
    ).all()
    assert any(e.to_status == "awaiting_payment" and e.from_status is None for e in events)

    assert (await get_order(db_session, user.id, order.id)) is not None
    assert order.id in [o.id for o in await list_orders(db_session, user.id)]


async def test_create_order_empty_cart_raises(db_session: AsyncSession) -> None:
    user, _ = await _seed(db_session)
    address = await _address(db_session, user.id)
    with pytest.raises(EmptyCart):
        await create_order(db_session, user_id=user.id, address=address)


async def test_create_order_no_address_raises(db_session: AsyncSession) -> None:
    user, product = await _seed(db_session)
    await add_item(db_session, user.id, product, 1)
    with pytest.raises(NoAddress):
        await create_order(db_session, user_id=user.id, address=None)


async def test_create_order_stock_guard(db_session: AsyncSession) -> None:
    user, product = await _seed(db_session, stock=3)
    await add_item(db_session, user.id, product, 2)
    address = await _address(db_session, user.id)

    # Someone else reserves the remaining unit before checkout.
    product.reserved_qty += 2
    await db_session.flush()

    with pytest.raises(StockChanged):
        await create_order(db_session, user_id=user.id, address=address)


async def test_cancel_releases_stock(db_session: AsyncSession) -> None:
    user, product = await _seed(db_session)
    await add_item(db_session, user.id, product, 3)
    address = await _address(db_session, user.id)
    order = await create_order(db_session, user_id=user.id, address=address)
    assert product.reserved_qty == 3

    assert await cancel_order(db_session, order, actor_telegram_id=user.telegram_id)
    await db_session.flush()
    assert order.status == "cancelled"
    assert order.cancelled_at is not None
    assert product.reserved_qty == 0

    events = (
        await db_session.scalars(
            select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id)
        )
    ).all()
    assert any(e.to_status == "cancelled" and e.from_status == "awaiting_payment" for e in events)

    # already-cancelled orders cannot be cancelled again
    assert not await cancel_order(db_session, order)
