"""Per-user shopping cart with price snapshots and stock-aware quantities."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Cart, CartItem, Product
from app.services.catalog import available


class CartError(Exception):
    pass


class OutOfStock(CartError):
    pass


class TooMany(CartError):
    pass


async def get_or_create_cart(session: AsyncSession, user_id: int) -> Cart:
    cart = await session.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None:
        cart = Cart(user_id=user_id)
        session.add(cart)
        await session.flush()
    return cart


async def list_items(session: AsyncSession, cart_id: int) -> list[CartItem]:
    return list(
        await session.scalars(
            select(CartItem).where(CartItem.cart_id == cart_id).order_by(CartItem.id)
        )
    )


async def add_item(session: AsyncSession, user_id: int, product: Product, qty: int = 1) -> CartItem:
    cart = await get_or_create_cart(session, user_id)
    item = await session.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product.id)
    )
    current = item.qty if item else 0
    target = current + qty
    if not 1 <= target <= 20:
        raise TooMany("qty must be between 1 and 20")
    free = available(product)
    if target > free:
        raise OutOfStock(f"only {free} left")
    if item is None:
        item = CartItem(
            cart_id=cart.id,
            product_id=product.id,
            qty=target,
            price_at_add_rial=product.price_rial,
        )
        session.add(item)
    else:
        item.qty = target
        # Refresh the price snapshot to the current price on every change.
        item.price_at_add_rial = product.price_rial
    await session.flush()
    return item


async def set_qty(session: AsyncSession, cart_id: int, item_id: int, qty: int) -> CartItem | None:
    item = await session.scalar(
        select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart_id)
    )
    if item is None:
        return None
    if qty <= 0:
        await session.delete(item)
        await session.flush()
        return None
    if qty > 20:
        raise TooMany("qty must be between 1 and 20")
    product = await session.get(Product, item.product_id)
    if product is None:
        raise OutOfStock("product no longer exists")
    if qty > available(product):
        raise OutOfStock(f"only {available(product)} left")
    item.qty = qty
    item.price_at_add_rial = product.price_rial
    await session.flush()
    return item


async def remove_item(session: AsyncSession, cart_id: int, item_id: int) -> bool:
    item = await session.scalar(
        select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart_id)
    )
    if item is None:
        return False
    await session.delete(item)
    await session.flush()
    return True


def subtotal(items: list[CartItem]) -> int:
    return sum(item.qty * item.price_at_add_rial for item in items)


async def clear(session: AsyncSession, cart_id: int) -> None:
    for item in await list_items(session, cart_id):
        await session.delete(item)
    await session.flush()
