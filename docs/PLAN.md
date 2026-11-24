# Implementation plan — fanic_bot

## 1. Goals

Build a Telegram shop bot that is:

- **Persian-first** — every user-facing string is Farsi, RTL-friendly, in one locale file.
- **Admin-gated** — a new user must confirm 18+, give name and Iranian phone number, and be
  approved by an admin before any shopping feature is reachable.
- **Self-contained** — catalog, cart, checkout, orders, wallet, card-to-card payment,
  fulfillment notifications, admin panel, broadcast and basic reports.
- **Safe with money** — all monetary values are integer **Rials** in PostgreSQL; every balance
  change and payment event is append-only and auditable; no double-spend and no double-match.
- **Deployable** — Docker Compose, long polling by default (webhook optional), migrations,
  structured logs, secrets from environment only.

The code is a **product-agnostic engine**: no product-specific wording is baked into code.
Category names, product descriptions and welcome copy live in `locales/fa.json` and the DB.
The operator is responsible for legal compliance of the goods they sell.

## 2. Tech stack (and why)

| Choice | Reason |
| --- | --- |
| **Python 3.12** | Modern typing, good async support. |
| **aiogram 3.34** | Best-in-class FSM, inline-keyboard/callback ergonomics, Russian/Iranian community, active maintenance; far better than python-telegram-bot for the many multi-step admin flows here. |
| **aiohttp 3** | Already used for `/healthz`; hosts the internal SMS webhook and (optionally) the Telegram webhook in the same process. |
| **PostgreSQL 16 + asyncpg + SQLAlchemy 2 async** | Money ledger needs real transactions, `SELECT … FOR UPDATE`, partial unique indexes and serializable constraints. SQLite was rejected. |
| **Alembic** | Versioned, reviewable schema migrations. |
| **Redis 7** | FSM state and rate-limit counters; code degrades to in-memory when Redis is absent (test/dev convenience). |
| **pydantic-settings** | Fail-fast, typed configuration; all secrets from env only. |
| **structlog** | JSON logs with a `mask()` helper for tokens/PANs/phones. |
| **uv** | Reproducible locked installs (`uv.lock` committed). |
| **pytest + pytest-asyncio + pytest-aiohttp** | Async unit and HTTP integration tests. |
| **ruff + mypy** | Lint/type gates in CI and before each commit. |

## 3. Architecture

```
Telegram user ──► aiogram Dispatcher ──► handlers ──► services ──► SQLAlchemy ──► Postgres
                        │                    │                        │
                     FSM in Redis        locale fa.json          Alembic migrations
                        │
Admin group ◄──── notifier service ◄──── events (signup, paid order, alerts)

Bank SMS (operator phone) ──► HTTPS POST /internal/sms
                                  │ HMAC + device id
                                  ▼
                          SMS parser ──► amount matcher ──► payment ledger
                                  │
                          receipt photo ──► admin manual approval (fallback)
```

Layering: `handlers` (Telegram I/O) → `services` (business rules, transactions) → `repositories`
(queries) → `models`. Handlers never open a transaction directly; services own the unit of work.

## 4. Currency model

- **Canonical unit:** integer **Rial**, stored in `*_rial` BIGINT columns. Displayed to users
  as **Toman** (`rial // 10`) with Persian digits.
- **Unique payment suffix:** the last 1–3 **Rials** of the transfer amount (`SUFFIX_MIN_TOMAN`
  … `SUFFIX_MAX_TOMAN` env config, mapped to Rial) identify a payment intent.
- Users are shown the *exact* amount to transfer (Toman + Rial suffix), so no ambiguity.

> Confirmation pending: Toman vs Rial display is an assumption (see DECISIONS.md).

## 5. Database schema summary

See `docs/DATABASE.md` for the authoritative field list. Tables:

- `users`, `user_events`, `addresses`
- `categories`, `products`, `product_images`, `carts`, `cart_items`
- `orders`, `order_items`, `order_status_history`
- `payment_intents`, `sms_messages`, `bank_transactions`, `shop_cards`,
  `payment_proofs`, `card_bindings`
- `wallet_transactions`, `admin_audit_log`, `broadcasts`, `broadcast_targets`,
  `support_threads`, `support_messages`, `jobs`, `settings`

All money is BIGINT Rial. Audit/log tables are append-only. Status transitions are constrained
by CHECK constraints and written to `*_history` tables.

## 6. Flows

### Signup
`/start` → age gate (18+ confirm, mandatory) → full name → phone (contact button, with
manual input + Iranian-number validation) → status `pending` → admins notified with
Approve/Reject inline buttons → user notified of outcome. `draft` users cannot use the shop.

### Ordering
Main menu → categories → product detail (photo, description, price, stock) → add to cart →
cart (qty edit/remove) → checkout (address select/create + note) → order created with
`awaiting_payment` → payment choice: wallet / card-to-card / mixed.

### Payment
A `payment_intent` is created with a **unique amount suffix** and a 15-minute expiry. The
customer sees card number, cardholder, exact amount and deadline. Matching sources:
1. forwarded bank SMS (HMAC-protected internal webhook) — automatic,
2. unique-amount match — automatic,
3. receipt photo → manual admin approval — fallback.
On match: ledger entry, order `paid`, admins notified. See `docs/PAYMENTS.md`.

### Fulfillment
Admin marks `preparing` → `shipped`/`out_for_delivery` → `delivered`; each change is recorded
with timestamp/actor. On shipped/delivered the customer is notified and asked to confirm receipt.

### Admin
Inline panel gated by `ADMIN_IDS` (plus `ADMIN_ROLES` for support vs owner): pending users,
product CRUD, order filter by status, payment log/manual approve, wallet adjust with reason,
broadcast, basic reports. Owner role only for money/broadcast/settings.

## 7. Milestones, branches and tags

| # | Milestone | Branch | Tag | Exit test |
| --- | --- | --- | --- | --- |
| M0 | Skeleton | `main` | `v0.1.0-skeleton` ✅ | `pytest` 4 green, `/healthz`, `docker compose config` |
| M1 | Data layer + migrations | `feature/data-layer` | `v0.2.0-data-layer` | models import, Alembic upgrade/downgrade on real Postgres, `pytest` green |
| M2 | Signup & verification | `feature/signup` | `v0.3.0-signup` | bot flow with 2 test users + admin approve/reject |
| M3 | Catalog & cart | `feature/catalog` | `v0.4.0-catalog` | browse → add → qty → remove with DB assertions |
| M4 | Checkout & orders | `feature/orders` | `v0.5.0-orders` | address + order creation, stock reservation, history |
| M5 | Payments & wallet | `feature/payments` | `v0.6.0-payments` | SMS match, expiry, partial, duplicate, receipt fallback |
| M6 | Admin panel | `feature/admin` | `v1.0.0-mvp` | full owner/support journey; MVP done |
| M7 | Fulfillment notifications | `feature/fulfillment` | `v1.1.0-fulfillment` | admin status → customer notification + confirmation |
| M8 | Broadcast, reports, support | `feature/extras` | `v1.2.0-extras` | broadcast to verified only, reports correct |
| M9 | Deploy & hardening | `feature/hardening` | `v1.3.0` | compose up on VPS, webhook + polling both tested |

MVP = M0–M6. Each milestone merges into `main` only after its tests pass, then is tagged.

## 8. Risks

See section 9 of the original brief and `docs/DECISIONS.md`. Main ones: card-to-card has no
official API; Telegram policy and local law for age-restricted goods; SMS forwarding
reliability; chargebacks/refunds; PII handling.

## 9. Documentation map

- `docs/TASKS.md` + `docs/tasks/` — task breakdown.
- `docs/ARCHITECTURE.md` — components, data flow, decisions.
- `docs/DATABASE.md` — schema reference.
- `docs/PAYMENTS.md` — payment matching design.
- `docs/DECISIONS.md` — decisions and open questions.
- `docs/CHANGELOG.md` — version history.
- `docs/legal-notes.fa.md` — operator compliance reminder (Farsi).
- `docs/progress.md` — running milestone log.
