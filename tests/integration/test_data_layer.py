"""M1: schema integrity — constraints that protect money and stock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BankTransaction,
    Cart,
    CartItem,
    Category,
    Order,
    PaymentIntent,
    Product,
    ShopCard,
    User,
    WalletTransaction,
)


def make_user(tg_id: int = 1001, **kw) -> User:
    return User(
        telegram_id=tg_id,
        full_name=kw.pop("full_name", "کاربر آزمایشی"),
        status=kw.pop("status", "verified"),
        **kw,
    )


def make_intent(user_id: int, amount: int, order_id: int | None = None, **kw) -> PaymentIntent:
    suffix = kw.pop("suffix_rial", 0)
    return PaymentIntent(
        token=uuid4(),
        user_id=user_id,
        purpose=kw.pop("purpose", "wallet_topup"),
        order_id=order_id,
        base_amount_rial=amount - suffix,
        suffix_rial=suffix,
        expected_amount_rial=amount,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        **kw,
    )


async def test_wallet_negative_balance_rejected(db_session: AsyncSession) -> None:
    db_session.add(make_user())
    await db_session.flush()
    db_session.add(
        WalletTransaction(
            user_id=1,
            amount_rial=-1,
            balance_after_rial=-1,
            type="admin_debit",
            idempotency_key="k1",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_wallet_idempotency_key_unique(db_session: AsyncSession) -> None:
    db_session.add(make_user())
    await db_session.flush()
    db_session.add(
        WalletTransaction(
            user_id=1,
            amount_rial=1000,
            balance_after_rial=1000,
            type="topup",
            idempotency_key="same-key",
        )
    )
    await db_session.flush()
    db_session.add(
        WalletTransaction(
            user_id=1,
            amount_rial=1000,
            balance_after_rial=2000,
            type="topup",
            idempotency_key="same-key",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_live_intent_amounts_must_be_unique(db_session: AsyncSession) -> None:
    db_session.add(make_user())
    await db_session.flush()
    db_session.add(make_intent(1, 100_010))
    await db_session.flush()
    db_session.add(make_intent(1, 100_010))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_expired_intent_frees_the_amount(db_session: AsyncSession) -> None:
    db_session.add(make_user())
    await db_session.flush()
    first = make_intent(1, 100_010, status="expired")
    db_session.add(first)
    await db_session.flush()
    db_session.add(make_intent(1, 100_010))
    await db_session.flush()  # no conflict: the first one is not live


async def test_one_live_intent_per_order(db_session: AsyncSession) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    order = Order(
        public_code="A1",
        user_id=user.id,
        subtotal_rial=100_000,
        delivery_fee_rial=0,
        total_rial=100_000,
        address_snapshot={"city": "تهران"},
    )
    db_session.add(order)
    await db_session.flush()
    db_session.add(make_intent(user.id, 100_010, order_id=order.id, purpose="order"))
    await db_session.flush()
    db_session.add(make_intent(user.id, 100_020, order_id=order.id, purpose="order"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_order_total_math_enforced(db_session: AsyncSession) -> None:
    db_session.add(make_user())
    await db_session.flush()
    db_session.add(
        Order(
            public_code="BAD",
            user_id=1,
            subtotal_rial=100_000,
            delivery_fee_rial=10_000,
            total_rial=100_000,  # should be 110_000
            address_snapshot={},
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_stock_reservation_cannot_exceed_stock(db_session: AsyncSession) -> None:
    cat = Category(slug="c", title_fa="دسته")
    db_session.add(cat)
    await db_session.flush()
    db_session.add(
        Product(
            category_id=cat.id,
            title_fa="کالا",
            price_rial=50_000,
            stock_qty=2,
            reserved_qty=3,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_cart_qty_range(db_session: AsyncSession) -> None:
    db_session.add(make_user())
    cat = Category(slug="c", title_fa="دسته")
    db_session.add(cat)
    await db_session.flush()
    product = Product(category_id=cat.id, title_fa="کالا", price_rial=50_000, stock_qty=10)
    db_session.add(product)
    cart = Cart(user_id=1)
    db_session.add(cart)
    await db_session.flush()
    db_session.add(
        CartItem(cart_id=cart.id, product_id=product.id, qty=21, price_at_add_rial=50_000)
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_bank_ref_number_dedupe_allows_multiple_nulls(db_session: AsyncSession) -> None:
    db_session.add(make_user())
    await db_session.flush()
    for _ in range(2):
        db_session.add(
            BankTransaction(
                bank_code="mellat",
                dest_card_last4="1234",
                amount_rial=10_000,
                ref_number=None,
                status="new",
            )
        )
    await db_session.flush()
    db_session.add(
        BankTransaction(
            bank_code="mellat",
            dest_card_last4="1234",
            amount_rial=10_000,
            ref_number="R1",
            status="new",
        )
    )
    await db_session.flush()
    db_session.add(
        BankTransaction(
            bank_code="mellat",
            dest_card_last4="1234",
            amount_rial=10_000,
            ref_number="R1",
            status="new",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_shop_card_bank_last4_unique(db_session: AsyncSession) -> None:
    for _ in range(2):
        db_session.add(
            ShopCard(
                bank_code="mellat",
                card_last4="1234",
                card_masked="6037-****-****-1234",
                holder_name_fa="فروشگاه",
            )
        )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_default_address_partial_unique(db_session: AsyncSession) -> None:
    from app.db.models import Address

    db_session.add(make_user())
    await db_session.flush()
    base = dict(
        user_id=1,
        receiver_name="گیرنده",
        receiver_phone="9123456789",
        province="تهران",
        city="تهران",
        address_line="خیابان نمونه پلاک ۱",
    )
    db_session.add(Address(**base, is_default=True))
    await db_session.flush()
    db_session.add(Address(**base, is_default=True))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_wallet_ledger_matches_balance(db_session: AsyncSession) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    for amount, key in ((50_000, "a"), (25_000, "b"), (-10_000, "c")):
        user.wallet_balance_rial += amount
        db_session.add(
            WalletTransaction(
                user_id=user.id,
                amount_rial=amount,
                balance_after_rial=user.wallet_balance_rial,
                type="topup" if amount > 0 else "order_payment",
                idempotency_key=key,
            )
        )
    await db_session.flush()
    total = await db_session.scalar(
        select(func.sum(WalletTransaction.amount_rial)).where(WalletTransaction.user_id == user.id)
    )
    assert total == user.wallet_balance_rial == 65_000
