# Changelog

## Unreleased

- None — all planned milestones are complete.

## v1.3.0 (2026-11-24)

- Migration-on-start entrypoint, VPS/webhook deployment docs, global error alerts.
- Hardening pass: validation, rate limits and ledger checks.

## v1.2.0-extras (2026-11-24)

- Broadcast to verified users, sales report and support channel.

## v1.1.0-fulfillment (2026-11-24)

- Fulfilment buttons in paid-order admin notices and customer delivery confirmations.

## v1.0.0-mvp (2026-11-24)

- MVP complete: signup, catalog/cart, checkout/orders, payments/wallet and the
  full in-bot admin panel.
- Admin product management, order status management, payment log, receipt review
  and wallet adjustments with audit trail.

## v0.6.0-payments (2026-11-24)

- Unique-amount payment intents, expiry and card instructions.
- HMAC SMS webhook + parser, deduplication and transactional matching.
- Receipt upload with admin approval and wallet ledger with idempotency.
- `payment_overpay` ledger type migration; 100 tests green, ruff/mypy clean.

## v0.5.0-orders (2026-11-24)

- Address wizard with validation and delivery notes.
- Atomic order creation with stock reservation, immutable item snapshots and
  status history; my orders and cancellation.
- 86 tests green, ruff/mypy clean.

## v0.4.0-catalog (2026-11-24)

- Catalog browsing with categories, product photos/descriptions, prices and stock.
- Cart with price snapshots, stock-aware quantities, remove/clear and totals.
- End-to-end shop flow tests; test DB fixtures now clean up reliably.

## v0.3.0-signup (2026-11-24)

- Single-file Farsi locale plus digit/name/phone/time helpers and locale-coverage tests.
- aiogram dispatcher with Redis/in-memory FSM, DB session middleware, admin guard
  and per-user rate limiting.
- Mandatory 18+ signup wizard with contact/manual phone and admin approval flow.
- Admin panel for pending users, approve/reject/block/unblock/search; signup notices
  to admins and the admin group.
- Fake Telegram transport for end-to-end handler tests; 70 tests green, ruff/mypy clean.
- Fixed env list parsing, Docker migration paths and idempotent dispatcher construction.
- Docs backfilled after plan approval: `PLAN.md`, `TASKS.md`, per-task files,
  `ARCHITECTURE.md`, `DATABASE.md`, `PAYMENTS.md`, `DECISIONS.md`, this changelog.

## v0.2.0-data-layer (2026-11-24)

- Full ORM schema with money-safe constraints and append-only ledgers.
- Alembic async migrations; upgrade/downgrade verified on real PostgreSQL.
- Seed and ledger-check scripts; 18 tests green (constraint + integrity tests).
- All M1 task files marked done.

## v0.1.0-skeleton (2026-11-24)

- Initial `git init` on `main`; `.gitignore`, `.env.example`, README.
- uv/Python 3.12 project with locked dependencies.
- Typed env config, structlog JSON logging with masking.
- aiohttp `/healthz`, Dockerfile, docker-compose (Postgres 16, Redis 7, bot).
- ruff, mypy and pytest wired; 4 smoke tests passing.
- User, catalog and order ORM models started in the working tree.
