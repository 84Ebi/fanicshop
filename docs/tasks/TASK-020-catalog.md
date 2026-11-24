# TASK-020 — Catalog browsing

**Status:** done

## Description
Browse active categories and products with photos, descriptions, prices and stock.

## Goal
Verified customers can discover products without any product-specific wording in code.

## Acceptance criteria
- [x] `app/services/catalog.py` queries active categories/products and first photo.
- [x] Product card shows photo (Telegram `file_id`), Farsi description, Toman price and stock.
- [x] Out-of-stock products cannot be added; navigation callbacks are compact (`cat:<id>`, `p:<id>`).
- [x] Integration + end-to-end handler tests.

## Files affected
`app/services/catalog.py`, `app/bot/handlers/user/shop.py`, `app/bot/keyboards/inline.py`,
`app/locales/fa.json`, `tests/integration/test_catalog_cart.py`, `tests/integration/test_shop_flow.py`.

## Test steps
`pytest -q` → 74 green; browse category → product in fake transport; assert caption/price.

## Final status
done.
