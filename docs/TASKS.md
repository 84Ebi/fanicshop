# Master task list

Status: `todo` | `in progress` | `done`. Tick `- [x]` only when the task file says `done`.

## M0 — Skeleton (tag `v0.1.0-skeleton`) ✅

- [x] `TASK-000` [Project skeleton](tasks/TASK-000-project-skeleton.md) — uv/Python 3.12, config, logging, `/healthz`, Docker, toolchain. **done**

## M1 — Data layer (tag `v0.2.0-data-layer`)

- [x] `TASK-001` [User & address models](tasks/TASK-001-user-models.md) — users, events, addresses with status constraints. **done**
- [x] `TASK-002` [Catalog & cart models](tasks/TASK-002-catalog-models.md) — categories, products, images, carts, cart items. **done**
- [x] `TASK-003` [Order models](tasks/TASK-003-order-models.md) — orders, immutable items, status history. **done**
- [x] `TASK-004` [Payment models](tasks/TASK-004-payment-models.md) — intents, SMS, bank tx, proofs, cards. **done**
- [x] `TASK-005` [Ops models](tasks/TASK-005-ops-models.md) — wallet ledger, audit, broadcast, support, jobs, settings. **done**
- [x] `TASK-006` [Alembic migrations](tasks/TASK-006-alembic-migrations.md) — initial revision, upgrade/downgrade on Postgres. **done**
- [x] `TASK-007` [Data layer tests](tasks/TASK-007-data-tests.md) — constraints, relationships, ledger invariants. **done**

## M2 — Signup & verification (tag `v0.3.0-signup`)

- [x] `TASK-010` [Localization file](tasks/TASK-010-localization.md) — all Farsi strings in `locales/fa.json`. **done**
- [x] `TASK-011` [FSM & rate limiting](tasks/TASK-011-fsm.md) — aiogram FSM with Redis + in-memory fallback, per-user limits. **done**
- [x] `TASK-012` [Signup flow](tasks/TASK-012-signup-flow.md) — age gate, name, phone contact/manual, pending state. **done**
- [x] `TASK-013` [Admin verification](tasks/TASK-013-admin-verification.md) — notification, approve/reject, user notice. **done**

## M3 — Catalog & cart (tag `v0.4.0-catalog`)

- [ ] `TASK-020` [Catalog browsing](tasks/TASK-020-catalog.md) — categories, product detail, stock display. **todo**
- [ ] `TASK-021` [Cart management](tasks/TASK-021-cart.md) — add, qty change, remove, totals. **todo**

## M4 — Checkout & orders (tag `v0.5.0-orders`)

- [ ] `TASK-030` [Address & notes](tasks/TASK-030-address.md) — saved addresses, create, select, delivery note. **todo**
- [ ] `TASK-031` [Order creation](tasks/TASK-031-orders.md) — stock reservation, snapshots, status history, my orders. **todo**

## M5 — Payments & wallet (tag `v0.6.0-payments`)

- [ ] `TASK-040` [Payment intents](tasks/TASK-040-payment-intents.md) — unique amount, expiry, card display. **todo**
- [ ] `TASK-041` [SMS ingestion](tasks/TASK-041-sms-webhook.md) — HMAC endpoint, parser, device id. **todo**
- [ ] `TASK-042` [Payment matching](tasks/TASK-042-matching.md) — amount match, partial, duplicate, late, expiry. **todo**
- [ ] `TASK-043` [Receipt fallback](tasks/TASK-043-receipt-fallback.md) — photo upload → admin approval. **todo**
- [ ] `TASK-044` [Wallet ledger](tasks/TASK-044-wallet.md) — top-up, pay, history, adjustments. **todo**

## M6 — Admin panel (tag `v1.0.0-mvp`)

- [ ] `TASK-050` [Admin guard & menu](tasks/TASK-050-admin-guard.md) — ID/role gating, panel entry. **todo**
- [ ] `TASK-051` [User management](tasks/TASK-051-admin-users.md) — pending list, approve/reject/block, details. **todo**
- [ ] `TASK-052` [Product management](tasks/TASK-052-admin-products.md) — CRUD, price, stock, photos, categories. **todo**
- [ ] `TASK-053` [Order management](tasks/TASK-053-admin-orders.md) — list/filter by status, status update. **todo**
- [ ] `TASK-054` [Payment log](tasks/TASK-054-admin-payments.md) — log view, manual approval. **todo**
- [ ] `TASK-055` [Wallet adjustments](tasks/TASK-055-admin-wallet.md) — manual credit/debit with reason. **todo**

## M7 — Fulfillment (tag `v1.1.0-fulfillment`)

- [ ] `TASK-060` [Fulfillment notices](tasks/TASK-060-fulfillment.md) — paid order → admin, status → customer. **todo**
- [ ] `TASK-061` [Receipt confirmation](tasks/TASK-061-confirmation.md) — customer confirms delivery. **todo**

## M8 — Extras (tag `v1.2.0-extras`)

- [ ] `TASK-070` [Broadcast](tasks/TASK-070-broadcast.md) — verified users only, progress + log. **todo**
- [ ] `TASK-071` [Reports & support](tasks/TASK-071-reports.md) — sales reports, support threads. **todo**
- [ ] `TASK-072` [Hardening pass](tasks/TASK-072-hardening.md) — validation, rate limits, admin alerts. **todo**

## M9 — Deploy (tag `v1.3.0`)

- [ ] `TASK-080` [Deployment docs](tasks/TASK-080-deploy.md) — VPS setup, env, webhook/polling switch. **todo**
- [ ] `TASK-081` [Monitoring](tasks/TASK-081-monitoring.md) — health, error alerts, backups. **todo**
