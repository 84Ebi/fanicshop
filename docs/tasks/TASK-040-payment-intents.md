# TASK-040 — Payment intents

**Status:** done

## Description
Unique-amount, expiring payment intents for orders and wallet top-ups.

## Goal
Every transfer can be tied to one intent without customer ambiguity.

## Acceptance criteria
- [x] `create_intent` allocates a random Rial suffix; partial unique index prevents live collisions.
- [x] `expire_stale` frees amounts on expiry; late payments can be escalated.
- [x] Farsi instructions show card (env), holder, exact amount, deadline and code.
- [x] Tests for unique amounts and invalid amounts.

## Files affected
`app/services/payments.py`, `app/services/wallet.py`, `app/bot/handlers/user/payments.py`,
`app/locales/fa.json`, tests.

## Test steps
`pytest -q` → intent uniqueness, expiry and display tests green.

## Final status
done.
