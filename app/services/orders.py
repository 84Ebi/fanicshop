"""Addresses, order creation, stock reservation and status history."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Address, Cart, Order, OrderItem, OrderStatusHistory, Product, User
from app.db.models.orders import ORDER_STATUSES
from app.services.cart import list_items, subtotal
from app.services.catalog import available
from app.utils.names import normalize_name
from app.utils.phone import normalize_phone

CANCELLABLE = ("awaiting_payment",)


class OrderError(Exception):
    pass


class EmptyCart(OrderError):
    pass


class StockChanged(OrderError):
    pass


class NoAddress(OrderError):
    pass


async def list_addresses(session: AsyncSession, user_id: int) -> list[Address]:
    return list(
        await session.scalars(
            select(Address)
            .where(Address.user_id == user_id, Address.is_deleted.is_(False))
            .order_by(Address.is_default.desc(), Address.id.desc())
        )
    )


async def get_address(session: AsyncSession, user_id: int, address_id: int) -> Address | None:
    return await session.scalar(
        select(Address).where(
            Address.id == address_id, Address.user_id == user_id, Address.is_deleted.is_(False)
        )
    )


async def create_address(
    session: AsyncSession,
    user_id: int,
    *,
    receiver_name: str,
    receiver_phone: str,
    province: str,
    city: str,
    address_line: str,
    postal_code: str | None = None,
    note: str | None = None,
) -> Address:
    name = normalize_name(receiver_name)
    phone = normalize_phone(receiver_phone)
    line = (address_line or "").strip()
    if name is None:
        raise ValueError("invalid receiver name")
    if phone is None:
        raise ValueError("invalid receiver phone")
    if len(line) < 5 or not province.strip() or not city.strip():
        raise ValueError("invalid address")

    existing = await list_addresses(session, user_id)
    address = Address(
        user_id=user_id,
        receiver_name=name,
        receiver_phone=phone,
        province=province.strip()[:60],
        city=city.strip()[:60],
        address_line=line[:300],
        postal_code=(postal_code or "").strip()[:10] or None,
        note=(note or "").strip()[:300] or None,
        is_default=not existing,
    )
    session.add(address)
    await session.flush()
    return address


def address_snapshot(address: Address) -> dict[str, Any]:
    return {
        "receiver_name": address.receiver_name,
        "receiver_phone": address.receiver_phone,
        "province": address.province,
        "city": address.city,
        "address_line": address.address_line,
        "postal_code": address.postal_code,
    }


def contact_snapshot(contact_kind: str, contact: str) -> dict[str, Any]:
    """Delivery contact stored on an order: a Telegram id or a phone number."""
    return {"contact_kind": contact_kind, "contact": contact}


def _public_code() -> str:
    stamp = datetime.now(UTC).strftime("%y%m%d")
    return f"F-{stamp}-{secrets.randbelow(1_000_000):06d}"


def _history(
    session: AsyncSession,
    order: Order,
    *,
    to_status: str,
    source: str,
    actor_telegram_id: int | None = None,
    note: str | None = None,
    from_status: str | None = None,
) -> None:
    session.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=from_status,
            to_status=to_status,
            source=source,
            actor_telegram_id=actor_telegram_id,
            note=note,
        )
    )


async def create_order(
    session: AsyncSession,
    *,
    user_id: int,
    contact_kind: str,
    contact: str,
    delivery_note: str | None = None,
    delivery_fee_rial: int = 0,
    actor_telegram_id: int | None = None,
) -> Order:
    cart = await session.scalar(select(Cart).where(Cart.user_id == user_id))
    items = await list_items(session, cart.id) if cart else []
    if not items:
        raise EmptyCart("cart is empty")
    if not contact:
        raise NoAddress("contact required")

    # Lock products and re-check stock before reserving.
    product_ids = [item.product_id for item in items]
    products: dict[int, Product] = {}
    for product_id in set(product_ids):
        product = await session.scalar(
            select(Product).where(Product.id == product_id).with_for_update()
        )
        if product is None:
            raise StockChanged(f"product {product_id} is gone")
        products[product_id] = product

    needed: dict[int, int] = {}
    for item in items:
        needed[item.product_id] = needed.get(item.product_id, 0) + item.qty
    for product_id, qty in needed.items():
        if available(products[product_id]) < qty:
            raise StockChanged(f"not enough stock for {product_id}")

    for product_id, qty in needed.items():
        products[product_id].reserved_qty += qty

    sub = subtotal(items)
    order = Order(
        public_code=_public_code(),
        user_id=user_id,
        status="awaiting_payment",
        payment_state="unpaid",
        subtotal_rial=sub,
        delivery_fee_rial=delivery_fee_rial,
        discount_rial=0,
        total_rial=sub + delivery_fee_rial,
        wallet_paid_rial=0,
        card_paid_rial=0,
        address_snapshot=contact_snapshot(contact_kind, contact),
        delivery_note=(delivery_note or "").strip()[:300] or None,
    )
    session.add(order)
    await session.flush()

    for item in items:
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                title_snapshot=products[item.product_id].title_fa,
                unit_price_rial=item.price_at_add_rial,
                qty=item.qty,
                line_total_rial=item.qty * item.price_at_add_rial,
            )
        )
    _history(
        session,
        order,
        to_status="awaiting_payment",
        source="user",
        actor_telegram_id=actor_telegram_id,
        from_status=None,
    )

    for item in items:
        await session.delete(item)
    await session.flush()
    return order


async def format_order(session: AsyncSession, order: Order) -> tuple[str, str]:
    """Return (items_text, address_text) for the order detail message."""
    from app.i18n import fa_digits, money_rial, t

    items = (
        await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))
    ).all()
    items_text = "\n".join(
        t(
            "order.item_line",
            title=item.title_snapshot,
            qty=fa_digits(item.qty),
            line=money_rial(item.line_total_rial),
        )
        for item in items
    )
    from app.utils.phone import display_phone

    snap = order.address_snapshot or {}
    if snap.get("contact_kind") == "phone":
        address_text = t(
            "orders.contact_phone",
            phone=fa_digits(display_phone(snap.get("contact", ""))),
        )
    elif snap.get("contact_kind") == "telegram_id":
        address_text = t("orders.contact_telegram_id", id=snap.get("contact", ""))
    else:
        address_text = t("orders.contact_none")
    loc = order.delivery_location or {}
    if loc.get("latitude") is not None:
        address_text += t("orders.delivery_location", label=loc.get("label") or "")
    return items_text, address_text


async def get_order(session: AsyncSession, user_id: int, order_id: int) -> Order | None:
    return await session.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
    )


async def list_orders_admin(
    session: AsyncSession,
    *,
    status: str | None = None,
    search: str | None = None,
    limit: int = 8,
    offset: int = 0,
) -> list[Order]:
    query = select(Order).order_by(Order.id.desc())
    if status and status != "all":
        query = query.where(Order.status == status)
    if search:
        like = f"%{search.strip()}%"
        query = query.join(User, Order.user_id == User.id).where(
            or_(
                Order.public_code.ilike(like),
                User.full_name.ilike(like),
                User.phone.ilike(like),
            )
        )
    return list((await session.scalars(query.limit(limit).offset(offset))).all())


async def count_orders_admin(
    session: AsyncSession,
    *,
    status: str | None = None,
    search: str | None = None,
) -> int:
    query = select(func.count()).select_from(Order)
    if status and status != "all":
        query = query.where(Order.status == status)
    if search:
        like = f"%{search.strip()}%"
        query = query.join(User, Order.user_id == User.id).where(
            or_(
                Order.public_code.ilike(like),
                User.full_name.ilike(like),
                User.phone.ilike(like),
            )
        )
    return int(await session.scalar(query) or 0)


async def list_orders(session: AsyncSession, user_id: int, *, limit: int = 20) -> list[Order]:
    return list(
        await session.scalars(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.id.desc())
            .limit(limit)
        )
    )


async def confirm_delivery(
    session: AsyncSession, order: Order, *, actor_telegram_id: int | None = None
) -> bool:
    """Customer confirms receipt of a shipped/delivered order."""
    if order.customer_confirmed_at is not None:
        return False
    if order.status not in ("shipped", "out_for_delivery", "delivered"):
        return False
    order.customer_confirmed_at = datetime.now(UTC)
    _history(
        session,
        order,
        to_status=order.status,
        source="user",
        actor_telegram_id=actor_telegram_id,
        note="customer confirmed receipt",
        from_status=order.status,
    )
    await session.flush()
    return True


async def set_order_status(
    session: AsyncSession, order: Order, status: str, *, actor_telegram_id: int | None = None
) -> bool:
    """Admin-driven status change with a history row. Returns True if changed."""
    if status not in ORDER_STATUSES or status == order.status:
        return False
    previous = order.status
    order.status = status
    if status == "shipped":
        order.shipped_at = datetime.now(UTC)
    elif status == "delivered":
        order.delivered_at = datetime.now(UTC)
    elif status == "cancelled":
        order.cancelled_at = datetime.now(UTC)
    _history(
        session,
        order,
        to_status=status,
        source="admin",
        actor_telegram_id=actor_telegram_id,
        from_status=previous,
    )
    await session.flush()
    return True


async def cancel_order(
    session: AsyncSession, order: Order, *, actor_telegram_id: int | None = None
) -> bool:
    if order.status not in CANCELLABLE:
        return False
    previous = order.status
    order.status = "cancelled"
    order.cancelled_at = datetime.now(UTC)
    order.cancel_reason = "cancelled_by_customer"
    for item in await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id)):
        if item.product_id is not None:
            product = await session.get(Product, item.product_id)
            if product is not None:
                product.reserved_qty = max(0, product.reserved_qty - item.qty)
    _history(
        session,
        order,
        to_status="cancelled",
        source="user",
        actor_telegram_id=actor_telegram_id,
        from_status=previous,
    )
    await session.flush()
    return True
