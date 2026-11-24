"""Verify the wallet ledger invariant: balance == SUM(transactions) for every user.

Exit code 1 if any mismatch (suitable for cron/health checks).

Usage: python -m scripts.check_ledger [--database-url ...]
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import User, WalletTransaction


async def find_mismatches(session: AsyncSession) -> list[tuple[int, int, int]]:
    ledger = (
        select(
            WalletTransaction.user_id,
            func.coalesce(func.sum(WalletTransaction.amount_rial), 0).label("total"),
        )
        .group_by(WalletTransaction.user_id)
        .subquery()
    )
    rows = await session.execute(
        select(
            User.id,
            User.wallet_balance_rial,
            func.coalesce(ledger.c.total, 0),
        ).outerjoin(ledger, ledger.c.user_id == User.id)
    )
    return [(uid, balance, int(total)) for uid, balance, total in rows if balance != total]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    engine = create_async_engine(args.database_url or get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as session:
            bad = await find_mismatches(session)
    finally:
        await engine.dispose()

    if bad:
        for uid, balance, total in bad:
            print(f"MISMATCH user={uid} balance={balance} ledger_sum={total}")
        return 1
    print("ledger ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
