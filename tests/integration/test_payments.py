"""M5: unique-amount intents, SMS matching, receipts, and wallet ledger."""

from __future__ import annotations

import hashlib
import secrets

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import (
    BankTransaction,
    Category,
    OrderStatusHistory,
    PaymentIntent,
    Product,
    SmsMessage,
    User,
)
from app.services.cart import add_item
from app.services.orders import create_address, create_order
from app.services.payments import (
    ParsedSms,
    attach_proof,
    create_intent,
    expire_stale,
    match_sms,
    pay_order_from_wallet,
    review_proof,
    settle_intent,
)
from app.services.wallet import credit, debit, history

SETTINGS = Settings(
    _env_file=None,
    bot_token="123456:TEST",
    shop_card_number="6037991234567890",
    shop_card_holder="علی رضایی",
    payment_window_minutes=15,
    suffix_min_toman=1,
    suffix_max_toman=999,
)


async def _make_order(session: AsyncSession, *, qty: int = 2, slug: str = "tea"):
    category = Category(slug=slug, title_fa="چای", sort_order=1)
    product = Product(
        category=category,
        title_fa="چای سبز",
        description_fa="دم کرده",
        price_rial=120_000,
        stock_qty=20,
        reserved_qty=0,
    )
    user = User(
        telegram_id=secrets.randbelow(10**9),
        full_name="علی رضایی",
        status="verified",
        phone=f"9{secrets.randbelow(10**9):09d}",
    )
    session.add_all([user, product])
    await session.flush()
    await add_item(session, user.id, product, qty)
    address = await create_address(
        session,
        user.id,
        receiver_name="علی رضایی",
        receiver_phone="09121234567",
        province="تهران",
        city="تهران",
        address_line="خیابان آزادی، پلاک ۱۲",
    )
    order = await create_order(session, user_id=user.id, address=address)
    return user, product, order


def _sms(session: AsyncSession, text: str) -> SmsMessage:
    sms = SmsMessage(
        raw_text=text,
        raw_hash=hashlib.sha256(text.encode()).hexdigest(),
        device_id="dev-1",
    )
    session.add(sms)
    return sms


async def test_create_intent_unique_amount_and_display(db_session: AsyncSession) -> None:
    user, _, order = await _make_order(db_session)
    a = await create_intent(
        db_session, user_id=user.id, amount_rial=order.total_rial, purpose="order",
        settings=SETTINGS, order_id=order.id,
    )
    assert a.status == "pending"
    assert a.token is not None
    assert a.resolved_at is None
    assert a.expected_amount_rial == a.base_amount_rial + a.suffix_rial

    # A different live intent never shares the exact amount with the first
    # (DB partial-unique index enforces this).
    _, _, order2 = await _make_order(db_session, qty=1, slug="tea2")
    b = await create_intent(
        db_session, user_id=user.id, amount_rial=order2.total_rial, purpose="order",
        settings=SETTINGS, order_id=order2.id,
    )
    assert b.expected_amount_rial != a.expected_amount_rial

    with pytest.raises(ValueError):
        await create_intent(
            db_session, user_id=user.id, amount_rial=0, purpose="order", settings=SETTINGS
        )


async def test_match_sms_matched_applies_payment(db_session: AsyncSession) -> None:
    user, _, order = await _make_order(db_session)
    intent = await create_intent(
        db_session, user_id=user.id, amount_rial=order.total_rial, purpose="order",
        settings=SETTINGS, order_id=order.id,
    )
    sms = _sms(db_session, "transfer")
    await db_session.flush()

    parsed = ParsedSms(
        amount_rial=intent.expected_amount_rial,
        ref_number="REF-1",
        bank_code="melli",
        dest_card_last4="7890",
    )
    outcome = await match_sms(db_session, parsed, sms)
    assert outcome == "matched"
    await db_session.flush()

    assert intent.status == "matched"
    assert intent.resolved_at is not None
    tx = await db_session.get(BankTransaction, intent.matched_bank_tx_id)
    assert tx is not None and tx.status == "matched"
    assert tx.amount_rial == intent.expected_amount_rial
    # order fully paid; the suffix surplus is kept in the wallet
    assert order.card_paid_rial == order.total_rial
    assert order.wallet_paid_rial == 0
    assert order.status == "paid"
    assert order.payment_state == "paid"
    surplus = intent.expected_amount_rial - order.total_rial
    assert surplus > 0
    assert (await db_session.get(User, user.id)).wallet_balance_rial == surplus
    events = (
        await db_session.scalars(
            select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id)
        )
    ).all()
    assert any(e.to_status == "paid" for e in events)


async def test_match_sms_unmatched_and_duplicate(db_session: AsyncSession) -> None:
    user, _, order = await _make_order(db_session)
    await create_intent(
        db_session, user_id=user.id, amount_rial=order.total_rial, purpose="order",
        settings=SETTINGS, order_id=order.id,
    )

    sms1 = _sms(db_session, "transfer 1")
    await db_session.flush()
    out1 = await match_sms(
        db_session,
        ParsedSms(amount_rial=1, ref_number="REF-X", bank_code="melli", dest_card_last4="0000"),
        sms1,
    )
    assert out1 == "unmatched"

    sms2 = _sms(db_session, "transfer 2")
    await db_session.flush()
    # now match for real
    intent = (
        await db_session.scalars(
            select(PaymentIntent).where(PaymentIntent.user_id == user.id)
        )
    ).one()
    out2 = await match_sms(
        db_session,
        ParsedSms(
            amount_rial=intent.expected_amount_rial, ref_number="REF-2",
            bank_code="melli", dest_card_last4="7890",
        ),
        sms2,
    )
    assert out2 == "matched"
    # same reference again -> duplicate
    sms3 = _sms(db_session, "transfer 3")
    await db_session.flush()
    out3 = await match_sms(
        db_session,
        ParsedSms(
            amount_rial=intent.expected_amount_rial, ref_number="REF-2",
            bank_code="melli", dest_card_last4="7890",
        ),
        sms3,
    )
    assert out3 == "duplicate"
    assert sms3.parse_status == "ignored"


async def test_expire_stale(db_session: AsyncSession) -> None:
    user, _, order = await _make_order(db_session)
    intent = await create_intent(
        db_session, user_id=user.id, amount_rial=order.total_rial, purpose="order",
        settings=SETTINGS, order_id=order.id,
    )
    intent.expires_at = intent.expires_at - __import__("datetime").timedelta(minutes=60)
    await db_session.flush()
    assert await expire_stale(db_session) >= 1
    assert intent.status == "expired"
    # cannot settle an expired intent
    assert not await settle_intent(db_session, intent, amount_rial=intent.expected_amount_rial)


async def test_wallet_idempotent_credit_and_debit_guard(db_session: AsyncSession) -> None:
    user, _, _ = await _make_order(db_session)
    await credit(
        db_session, user_id=user.id, amount_rial=10_000, tx_type="topup",
        idempotency_key="k1", reason="x",
    )
    await credit(
        db_session, user_id=user.id, amount_rial=10_000, tx_type="topup",
        idempotency_key="k1", reason="x",
    )
    assert user.wallet_balance_rial == 10_000

    with pytest.raises(Exception) as exc:
        await debit(
            db_session, user_id=user.id, amount_rial=99_000, tx_type="spend",
            idempotency_key="k2", reason="y",
        )
    assert exc.type.__name__ == "InsufficientFunds"
    assert user.wallet_balance_rial == 10_000

    rows = await history(db_session, user.id)
    assert len(rows) == 1  # idempotency prevented the duplicate credit


async def test_pay_order_from_wallet_full_and_partial(db_session: AsyncSession) -> None:
    user, _, order = await _make_order(db_session, qty=1)  # total 120000
    await credit(
        db_session, user_id=user.id, amount_rial=50_000, tx_type="topup",
        idempotency_key="w1", reason="top",
    )
    used = await pay_order_from_wallet(db_session, order, user.id)
    assert used == 50_000
    assert order.wallet_paid_rial == 50_000
    assert order.payment_state == "partially_paid"

    await credit(
        db_session, user_id=user.id, amount_rial=200_000, tx_type="topup",
        idempotency_key="w2", reason="top2",
    )
    used2 = await pay_order_from_wallet(db_session, order, user.id)
    assert used2 == 70_000
    assert order.wallet_paid_rial == 120_000
    assert order.status == "paid"


async def test_receipt_attach_and_review(db_session: AsyncSession) -> None:
    user, _, order = await _make_order(db_session)
    intent = await create_intent(
        db_session, user_id=user.id, amount_rial=order.total_rial, purpose="order",
        settings=SETTINGS, order_id=order.id,
    )
    proof = await attach_proof(db_session, intent, file_id="AgAC_photo")
    await db_session.flush()
    assert proof.status == "pending"
    assert intent.status == "awaiting_review"

    assert await review_proof(db_session, proof, approve=True, actor=9001)
    await db_session.flush()
    assert proof.status == "approved"
    assert intent.status == "matched"
    assert order.status == "paid"

    # double review is ignored
    assert not await review_proof(db_session, proof, approve=False, actor=9001)


async def test_receipt_reject_cancels(db_session: AsyncSession) -> None:
    user, _, order = await _make_order(db_session)
    intent = await create_intent(
        db_session, user_id=user.id, amount_rial=order.total_rial, purpose="order",
        settings=SETTINGS, order_id=order.id,
    )
    proof = await attach_proof(db_session, intent, file_id="AgAC_photo")
    await db_session.flush()
    assert await review_proof(db_session, proof, approve=False, actor=9001, reason="fake")
    await db_session.flush()
    assert proof.status == "rejected"
    assert intent.status == "cancelled"
    assert order.status != "paid"
