"""Wallet ledger: every balance change is an append-only, idempotent row."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, WalletTransaction
from app.services.audit import audit


class InsufficientFunds(Exception):
    pass


async def get_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id, with_for_update=True)
    if user is None:
        raise ValueError("user not found")
    return user


async def change_balance(
    session: AsyncSession,
    *,
    user_id: int,
    amount_rial: int,
    tx_type: str,
    idempotency_key: str,
    reason: str | None = None,
    ref_type: str | None = None,
    ref_id: int | None = None,
    actor_telegram_id: int | None = None,
) -> WalletTransaction:
    """Apply a signed delta once. The unique key prevents double-crediting."""
    if amount_rial == 0:
        raise ValueError("amount must be non-zero")
    existing = await session.scalar(
        select(WalletTransaction).where(WalletTransaction.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing

    user = await get_user(session, user_id)
    new_balance = user.wallet_balance_rial + amount_rial
    if new_balance < 0:
        raise InsufficientFunds("wallet balance would go negative")
    user.wallet_balance_rial = new_balance
    tx = WalletTransaction(
        user_id=user_id,
        amount_rial=amount_rial,
        balance_after_rial=new_balance,
        type=tx_type,
        ref_type=ref_type,
        ref_id=ref_id,
        idempotency_key=idempotency_key,
        reason=reason,
        actor_telegram_id=actor_telegram_id,
    )
    session.add(tx)
    await session.flush()
    return tx


async def credit(
    session: AsyncSession, *, user_id: int, amount_rial: int, **kwargs: object
) -> WalletTransaction:
    if amount_rial <= 0:
        raise ValueError("credit amount must be positive")
    return await change_balance(session, user_id=user_id, amount_rial=amount_rial, **kwargs)  # type: ignore[arg-type]


async def debit(
    session: AsyncSession, *, user_id: int, amount_rial: int, **kwargs: object
) -> WalletTransaction:
    if amount_rial <= 0:
        raise ValueError("debit amount must be positive")
    return await change_balance(session, user_id=user_id, amount_rial=-amount_rial, **kwargs)  # type: ignore[arg-type]


async def history(
    session: AsyncSession, user_id: int, *, limit: int = 20
) -> list[WalletTransaction]:
    return list(
        await session.scalars(
            select(WalletTransaction)
            .where(WalletTransaction.user_id == user_id)
            .order_by(WalletTransaction.id.desc())
            .limit(limit)
        )
    )


async def admin_adjust(
    session: AsyncSession,
    *,
    user_id: int,
    amount_rial: int,
    reason: str,
    actor_telegram_id: int,
) -> WalletTransaction:
    import uuid

    tx = await change_balance(
        session,
        user_id=user_id,
        amount_rial=amount_rial,
        tx_type="admin_credit" if amount_rial > 0 else "admin_debit",
        idempotency_key=f"admin:{uuid.uuid4()}",
        reason=reason,
        actor_telegram_id=actor_telegram_id,
        ref_type="admin",
    )
    await audit(
        session,
        actor_telegram_id=actor_telegram_id,
        action="wallet.adjust",
        entity_type="user",
        entity_id=user_id,
        after={"amount_rial": amount_rial, "reason": reason},
    )
    return tx
