"""Payment intents, card-to-card matching and proof review."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import (
    BankTransaction,
    Order,
    OrderStatusHistory,
    PaymentIntent,
    PaymentProof,
    SmsMessage,
)
from app.i18n import money_rial, t
from app.logging import get_logger
from app.services.wallet import credit

log = get_logger("payments")

LIVE = ("pending", "awaiting_review")


@dataclass(frozen=True)
class ParsedSms:
    amount_rial: int
    ref_number: str | None
    bank_code: str
    dest_card_last4: str | None
    source_card_last4: str | None = None
    sender_name: str | None = None
    transferred_at: datetime | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _suffix(settings: Settings) -> int:
    low = max(1, settings.suffix_min_toman) * 10
    high = max(low, settings.suffix_max_toman) * 10
    return secrets.randbelow(high - low + 1) + low


async def create_intent(
    session: AsyncSession,
    *,
    user_id: int,
    amount_rial: int,
    purpose: str,
    settings: Settings,
    order_id: int | None = None,
) -> PaymentIntent:
    """Create a unique-amount intent. Retries if the suffix is already live."""
    if amount_rial <= 0:
        raise ValueError("amount must be positive")
    await expire_stale(session)
    last_error: Exception | None = None
    for _ in range(12):
        suffix = _suffix(settings)
        intent = PaymentIntent(
            token=uuid.uuid4(),
            user_id=user_id,
            purpose=purpose,
            order_id=order_id,
            provider="card_to_card",
            base_amount_rial=amount_rial,
            suffix_rial=suffix,
            expected_amount_rial=amount_rial + suffix,
            status="pending",
            expires_at=_now() + timedelta(minutes=settings.payment_window_minutes),
            attempt_no=1,
        )
        session.add(intent)
        try:
            await session.flush()
            return intent
        except IntegrityError as exc:
            await session.rollback()
            last_error = exc
    raise RuntimeError(f"could not allocate a unique payment amount: {last_error}")


async def expire_stale(session: AsyncSession) -> int:
    stale = (
        await session.scalars(
            select(PaymentIntent).where(
                PaymentIntent.status == "pending", PaymentIntent.expires_at < _now()
            )
        )
    ).all()
    for intent in stale:
        intent.status = "expired"
        intent.resolved_at = _now()
    if stale:
        await session.flush()
    return len(stale)


async def get_intent(session: AsyncSession, intent_id: int) -> PaymentIntent | None:
    return await session.get(PaymentIntent, intent_id)


async def latest_intent_for_order(session: AsyncSession, order_id: int) -> PaymentIntent | None:
    return await session.scalar(
        select(PaymentIntent)
        .where(PaymentIntent.order_id == order_id)
        .order_by(PaymentIntent.id.desc())
        .limit(1)
    )


def intent_display(intent: PaymentIntent, settings: Settings) -> str:
    deadline = intent.expires_at.astimezone() if intent.expires_at.tzinfo else intent.expires_at
    return t(
        "pay.instructions",
        card=settings.shop_card_number or "-",
        holder=settings.shop_card_holder or "-",
        amount=money_rial(intent.expected_amount_rial),
        exact=str(intent.expected_amount_rial),
        deadline=deadline.strftime("%H:%M"),
        code=str(intent.token)[:8],
        suffix=money_rial(intent.suffix_rial),
    )


def _history(
    session: AsyncSession, order: Order, to_status: str, actor: int | None,
    note: str | None = None,
) -> None:
    session.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=order.status,
            to_status=to_status,
            source="system",
            actor_telegram_id=actor,
            note=note,
        )
    )


async def apply_order_payment(
    session: AsyncSession, order: Order, amount_rial: int, *, source: str, actor: int | None = None
) -> None:
    """Add a payment to an order and promote its status when fully paid."""
    if source == "wallet":
        order.wallet_paid_rial += amount_rial
    else:
        order.card_paid_rial += amount_rial
    paid = order.wallet_paid_rial + order.card_paid_rial
    if paid >= order.total_rial:
        if order.status != "paid":
            _history(session, order, "paid", actor)
            order.status = "paid"
        order.payment_state = "paid"
    else:
        order.payment_state = "partially_paid"
    await session.flush()


async def pay_order_from_wallet(
    session: AsyncSession, order: Order, user_id: int, *, actor: int | None = None
) -> int:
    """Use as much wallet balance as possible; returns the amount used."""
    from app.services.wallet import debit, get_user

    user = await get_user(session, user_id)
    remaining = max(0, order.total_rial - order.wallet_paid_rial - order.card_paid_rial)
    use = min(remaining, user.wallet_balance_rial)
    if use <= 0:
        return 0
    await debit(
        session,
        user_id=user_id,
        amount_rial=use,
        tx_type="order_payment",
        idempotency_key=f"order:wallet:{order.id}:{use}:{order.wallet_paid_rial}",
        reason=f"order {order.public_code}",
        ref_type="order",
        ref_id=order.id,
        actor_telegram_id=actor,
    )
    await apply_order_payment(session, order, use, source="wallet", actor=actor)
    return use


async def settle_intent(
    session: AsyncSession,
    intent: PaymentIntent,
    *,
    amount_rial: int,
    bank_tx: BankTransaction | None = None,
    actor: int | None = None,
) -> bool:
    """Mark an intent matched and apply the payment. Returns False if already settled."""
    if intent.status not in LIVE:
        return False
    intent.status = "matched"
    intent.resolved_at = _now()
    if bank_tx is not None:
        bank_tx.status = "matched"
        bank_tx.matched_intent_id = intent.id
        bank_tx.attributed_user_id = intent.user_id
        intent.matched_bank_tx_id = bank_tx.id

    if intent.purpose == "wallet_topup":
        await credit(
            session,
            user_id=intent.user_id,
            amount_rial=amount_rial,
            tx_type="topup",
            idempotency_key=f"intent:{intent.id}",
            reason="card-to-card top-up",
            ref_type="intent",
            ref_id=intent.id,
            actor_telegram_id=actor,
        )
    elif intent.order_id is not None:
        order = await session.get(Order, intent.order_id)
        if order is not None:
            remaining = max(
                0,
                order.total_rial - order.wallet_paid_rial - order.card_paid_rial,
            )
            applied = min(amount_rial, remaining)
            if applied > 0:
                await apply_order_payment(session, order, applied, source="card", actor=actor)
            # The unique-amount suffix can exceed the order total; the surplus
            # is kept in the customer's wallet rather than silently lost.
            surplus = amount_rial - applied
            if surplus > 0:
                await credit(
                    session,
                    user_id=intent.user_id,
                    amount_rial=surplus,
                    tx_type="payment_overpay",
                    idempotency_key=f"intent:overpay:{intent.id}",
                    reason=f"overpayment of {intent.token}",
                    ref_type="intent",
                    ref_id=intent.id,
                    actor_telegram_id=actor,
                )
    await session.flush()
    return True


async def match_sms(session: AsyncSession, parsed: ParsedSms, sms: SmsMessage) -> str:
    """Match a parsed bank SMS to exactly one live intent. Returns the outcome."""
    # Deduplicate by bank + reference number (partial unique index).
    existing = await session.scalar(
        select(BankTransaction).where(
            BankTransaction.bank_code == parsed.bank_code,
            BankTransaction.ref_number == parsed.ref_number,
        )
    ) if parsed.ref_number else None
    if existing is not None:
        sms.parse_status = "ignored"
        await session.flush()
        return "duplicate"

    tx = BankTransaction(
        sms_message_id=sms.id,
        bank_code=parsed.bank_code,
        dest_card_last4=parsed.dest_card_last4 or "----",
        amount_rial=parsed.amount_rial,
        source_card_last4=parsed.source_card_last4,
        sender_name=parsed.sender_name,
        ref_number=parsed.ref_number,
        transferred_at=parsed.transferred_at,
        status="new",
    )
    session.add(tx)
    await session.flush()

    candidates = (
        await session.scalars(
            select(PaymentIntent)
            .where(
                PaymentIntent.status.in_(LIVE),
                PaymentIntent.expected_amount_rial == parsed.amount_rial,
            )
            .order_by(PaymentIntent.expires_at)
            .with_for_update(skip_locked=True)
        )
    ).all()
    if len(candidates) > 1:
        tx.status = "unmatched"
        tx.note = "ambiguous amount"
        sms.parse_status = "parsed"
        await session.flush()
        log.error("ambiguous_payment_match", amount_rial=parsed.amount_rial)
        return "ambiguous"
    if not candidates:
        tx.status = "unmatched"
        sms.parse_status = "parsed"
        await session.flush()
        log.warning("unmatched_payment", amount_rial=parsed.amount_rial)
        return "unmatched"

    await settle_intent(session, candidates[0], amount_rial=parsed.amount_rial, bank_tx=tx)
    sms.parse_status = "parsed"
    await session.flush()
    return "matched"


async def attach_proof(
    session: AsyncSession, intent: PaymentIntent, *, file_id: str, message_id: int | None = None
) -> PaymentProof:
    proof = PaymentProof(
        intent_id=intent.id,
        telegram_file_id=file_id,
        telegram_message_id=message_id,
        status="pending",
    )
    session.add(proof)
    if intent.status == "pending":
        intent.status = "awaiting_review"
    await session.flush()
    return proof


async def review_proof(
    session: AsyncSession,
    proof: PaymentProof,
    *,
    approve: bool,
    actor: int,
    reason: str | None = None,
) -> bool:
    if proof.status != "pending":
        return False
    proof.status = "approved" if approve else "rejected"
    proof.reviewed_by = actor
    proof.reviewed_at = _now()
    proof.reject_reason = None if approve else (reason or "not provided")
    intent = await session.get(PaymentIntent, proof.intent_id)
    if approve and intent is not None:
        await settle_intent(session, intent, amount_rial=intent.expected_amount_rial, actor=actor)
    elif intent is not None and intent.status == "awaiting_review":
        intent.status = "cancelled"
        intent.resolved_at = _now()
    await session.flush()
    return True
