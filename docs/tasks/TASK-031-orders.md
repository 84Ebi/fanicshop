# TASK-031 — Order creation & history

**Status:** done

## Description
Create orders from the cart with stock reservation, immutable items and status history.

## Goal
Order totals and snapshots are stable; stock is reserved atomically; customers can review and cancel.

## Acceptance criteria
- [x] `create_order` re-checks stock with `SELECT … FOR UPDATE`, reserves units, snapshots
      product titles/prices and address, and clears the cart.
- [x] `public_code` unique, `total = subtotal + delivery - discount`, status history appended.
- [x] Cancel only while awaiting payment; releases reserved stock and records history.
- [x] My orders list and order detail in Farsi with status labels.
- [x] Real-Postgres and end-to-end tests.

## Files affected
`app/services/orders.py`, `app/bot/handlers/user/orders.py`, `app/config.py`,
`app/locales/fa.json`, tests.

## Test steps
`pytest -q` → 86 green; verify reservation/cancel release and status history rows.

## Final status
done.
