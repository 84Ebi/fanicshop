# TASK-030 — Address & delivery notes

**Status:** done

## Description
Saved delivery addresses with validation and a delivery-note step at checkout.

## Goal
Orders carry a complete, auditable address snapshot and optional customer note.

## Acceptance criteria
- [x] `create_address` validates Iranian mobile, Persian receiver name, city/province and line.
- [x] First address becomes default; soft delete keeps order snapshots intact.
- [x] Checkout can select a saved address or create a new one; note can be skipped.
- [x] Farsi prompts and errors for every step.

## Files affected
`app/services/orders.py`, `app/bot/handlers/user/orders.py`, `app/bot/states.py`,
`app/locales/fa.json`, tests.

## Test steps
`pytest -q` → address wizard e2e and service validation tests green.

## Final status
done.
