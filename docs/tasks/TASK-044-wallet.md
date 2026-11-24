# TASK-044 — Wallet ledger

**Status:** done

## Description
Append-only wallet ledger with idempotent credits/debits and admin adjustments.

## Goal
`users.wallet_balance_rial` always equals the sum of the ledger; no double-spend.

## Acceptance criteria
- [x] Signed `amount_rial`, `balance_after_rial`, unique `idempotency_key`, reason/ref/actor.
- [x] Debit rejects insufficient funds; credit/debit helpers validate sign.
- [x] Wallet payment, top-up and admin adjustment use the same ledger.
- [x] Wallet menu, top-up flow and transaction history in Farsi.

## Files affected
`app/services/wallet.py`, `app/bot/handlers/user/payments.py`, `app/db/models/ops.py`, tests.

## Test steps
`pytest -q`; idempotent credit, negative balance guard, ledger-sum invariant tests green.

## Final status
done.
