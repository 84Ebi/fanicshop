# TASK-060 — Fulfillment notices

**Status:** done

## Description
Paid orders notify admins with item/customer/address details and fulfilment buttons.

## Goal
Admins can act on a paid order directly from the notification.

## Acceptance criteria
- [x] Admin notification includes order details and "ارسال شد" / "تحویل داده شد" buttons.
- [x] Buttons move the order to `shipped` / `delivered` with history rows.
- [x] Customer receives a Farsi notice with a receipt-confirmation button.
- [x] Status changes are timestamped and audited.

## Files affected
`app/bot/handlers/admin/shop.py`, `app/bot/handlers/user/payments.py`,
`app/bot/keyboards/inline.py`, `app/locales/fa.json`.

## Final status
done.
