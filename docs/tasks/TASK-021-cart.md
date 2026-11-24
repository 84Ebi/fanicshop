# TASK-021 — Cart management

**Status:** done

## Description
Add to cart, change quantity, remove, clear and compute totals with price snapshots.

## Goal
A cart reflects available stock and preserves the price shown to the customer.

## Acceptance criteria
- [x] `app/services/cart.py`: get-or-create cart, add, set qty, remove, clear, subtotal.
- [x] qty limited to 1–20 and to `stock_qty - reserved_qty`.
- [x] Price snapshot refreshed on quantity change.
- [x] Inline controls for +/-/remove/checkout/clear; Farsi empty-cart and error messages.
- [x] Tests for stock/qty limits and handler flow.

## Files affected
`app/services/cart.py`, `app/bot/handlers/user/shop.py`, `app/bot/keyboards/inline.py`,
`app/locales/fa.json`, tests.

## Test steps
`pytest -q`; add 2, increase to 3, view total, remove; assert DB rows and messages.

## Final status
done.
