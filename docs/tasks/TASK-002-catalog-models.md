# TASK-002 — Catalog & cart models

**Status:** done

## Description
Categories, products, images, carts and cart items.

## Goal
Support product CRUD with stock/reservation and per-user carts with price snapshots.

## Acceptance criteria
- [x] `Category` slug/title_fa/sort/active.
- [x] `Product` price_rial, stock_qty, reserved_qty, active, archive; CHECK stock >= reserved >= 0.
- [x] `ProductImage` Telegram `file_id` (no bytes stored).
- [x] `Cart`/`CartItem` unique per (cart, product), qty 1–20, price-at-add snapshot.

## Files affected
`app/db/models/catalog.py`.

## Test steps
Create category/product/image/cart/item; assert unique index and stock check constraints fire.

## Final status
done.
