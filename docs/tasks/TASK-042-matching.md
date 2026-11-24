# TASK-042 — Payment matching

**Status:** done

## Description
Match parsed bank transfers to live intents inside a transaction with dedupe and edge cases.

## Goal
No double-credit, no silent overpayment, no guessing on ambiguous amounts.

## Acceptance criteria
- [x] `match_sms` dedupes bank+reference, locks candidate intents (`SKIP LOCKED`).
- [x] Exact amount → settle; unmatched/ambiguous logged and admins alerted.
- [x] Overpayment surplus is credited to the customer's wallet (`payment_overpay` ledger type).
- [x] Expired intents are ignored and admins alerted for late payments.
- [x] Order status advances to paid/partially_paid with history rows.

## Files affected
`app/services/payments.py`, `app/db/models/ops.py`, `migrations/versions/`, tests.

## Test steps
`pytest -q`; match, unmatched, duplicate, expiry, overpay tests green.

## Final status
done.
