# TASK-055 — Wallet adjustments

**Status:** done

## Description
Manual admin credit/debit with a mandatory reason, recorded in the wallet ledger and audit log.

## Goal
Support staff can correct balances without bypassing the append-only ledger.

## Acceptance criteria
- [x] `/credit <user_id> <toman> <reason>` applies a signed adjustment.
- [x] Signed amount, reason, actor and audit row are stored.
- [x] Owner role only (admin guard).

## Files affected
`app/bot/handlers/admin/shop.py`, `app/services/wallet.py`, `app/locales/fa.json`, tests.

## Test steps
`pytest -q tests/integration/test_admin_shop_flow.py` → balance and ledger row asserted.

## Final status
done.
