# TASK-052 — Product management

**Status:** done

## Description
Admin product/category CRUD: create categories and products, edit price/stock, archive.

## Goal
The catalog is managed entirely from the bot, with Farsi prompts and validated amounts.

## Acceptance criteria
- [x] `/products` shows categories; new category slug/title wizard.
- [x] New product wizard: title, description, price (Toman → Rial), stock, optional photo.
- [x] Edit price/stock and archive; stock cannot drop below reserved units.
- [x] Admin-only via `ADMIN_IDS` + role guard.
- [x] End-to-end admin flow test.

## Files affected
`app/bot/handlers/admin/shop.py`, `app/services/catalog.py`, `app/bot/states.py`,
`app/locales/fa.json`, tests.

## Test steps
`pytest -q tests/integration/test_admin_shop_flow.py` → category + product created.

## Final status
done.
