# TASK-053 — Order management

**Status:** done

## Description
Admin order list with status filtering, status updates and customer notification.

## Goal
Admins can fulfil orders from inside the bot and every change is recorded.

## Acceptance criteria
- [x] `/orders` + inline filter by status; order detail with items and address.
- [x] Status buttons: preparing, shipped, out_for_delivery, delivered, cancelled.
- [x] `set_order_status` appends `order_status_history` with admin actor and timestamp.
- [x] Customer is notified in Farsi on status change.

## Files affected
`app/bot/handlers/admin/shop.py`, `app/services/orders.py`, `app/locales/fa.json`.

## Test steps
Admin `/orders` → filter → status change → DB history + customer message.

## Final status
done.
