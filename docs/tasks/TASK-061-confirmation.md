# TASK-061 — Receipt confirmation

**Status:** done

## Description
Customer confirms receipt of a shipped/delivered order with one inline button.

## Goal
Delivery is acknowledged and recorded with a timestamp.

## Acceptance criteria
- [x] `dc:<order_id>` sets `customer_confirmed_at` and appends a history note.
- [x] Only shipped/out_for_delivery/delivered orders can be confirmed.
- [x] Double confirmation is ignored with a Farsi message.

## Files affected
`app/bot/handlers/user/orders.py`, `app/services/orders.py`, `app/locales/fa.json`.

## Final status
done.
