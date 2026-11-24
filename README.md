# fanic_bot

A product-agnostic, age-restricted shop Telegram bot engine. All customer- and
admin-facing text is Persian and lives in `app/locales/fa.json`.

**Features (planned):** admin-gated signup (18+), catalog/cart/checkout/orders,
wallet and card-to-card payment verification via unique amounts + forwarded bank
SMS with a receipt fallback, fulfillment notifications, admin panel, broadcast
and basic reports.

**Important.** The codebase is intentionally free of product-specific wording.
Categories, products and welcome text live in the locale file and the database.
The operator is responsible for legal compliance (see `docs/legal-notes.fa.md`).

## Stack

- Python 3.12, aiogram 3.34, aiohttp 3
- PostgreSQL 16 (asyncpg, SQLAlchemy 2 async, Alembic migrations)
- Redis 7 (FSM state; in-memory fallback when unavailable)
- Docker Compose for local + production; long polling by default, webhook ready

## Setup

```bash
cp .env.example .env        # fill in secrets; .env is gitignored
uv sync --group dev         # or: docker compose up -d --build
alembic upgrade head        # migrations (also runnable in the container)
python -m app.main          # long polling + /healthz on :8080
curl localhost:8080/healthz
```

> In this sandbox `UV_NO_CONFIG=1` is required for all `uv` commands.

### Environment variables

See `.env.example` for the full list. Required: `BOT_TOKEN`. Important:
`ADMIN_IDS`, `ADMIN_ROLES`, `ADMIN_GROUP_CHAT_ID`, `DATABASE_URL`, `REDIS_URL`,
`SHOP_CARD_NUMBER` / `SHOP_CARD_HOLDER` (env only — never stored in the DB),
`SMS_HMAC_SECRET`, `SMS_DEVICE_IDS`, payment window and suffix ranges.

**Never commit real tokens, card numbers or user data.** If a token is ever
exposed, revoke it in BotFather and put the new one only in the local `.env`.

## Admin panel

Admins are Telegram user IDs from `ADMIN_IDS`. Send `/admin` to the bot to open
the panel: pending registrations, user search, approve/reject/block/unblock.
Every new signup also sends admins (and `ADMIN_GROUP_CHAT_ID`) a notification
with Approve/Reject buttons. `ADMIN_ROLES` distinguishes `owner` from `support`;
money/broadcast/settings will be owner-only.

## Tests

```bash
UV_NO_CONFIG=1 uv run pytest -q
UV_NO_CONFIG=1 uv run ruff check .
UV_NO_CONFIG=1 uv run mypy app scripts
```

Integration tests create/upgrade a throwaway PostgreSQL database
(`TEST_DATABASE_URL`, default `postgresql+asyncpg://fanic@127.0.0.1:55432/fanic_test`).
Unit and end-to-end handler tests use a fake Telegram transport.

## Documentation

`docs/PLAN.md` (approved plan), `docs/TASKS.md` + `docs/tasks/` (task list),
`docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/PAYMENTS.md`,
`docs/DECISIONS.md`, `docs/CHANGELOG.md`, `docs/legal-notes.fa.md`.

## Deployment (VPS)

1. Point a domain at the VPS if you want webhook mode; otherwise long polling
   works with no domain or TLS.
2. `cp .env.example .env` and fill in **all** secrets, especially `BOT_TOKEN`,
   `ADMIN_IDS`, `SHOP_CARD_NUMBER`, `SMS_HMAC_SECRET` and `SMS_DEVICE_IDS`.
   Revoke any token that was ever pasted into a chat.
3. `docker compose up -d --build`. The bot container runs `alembic upgrade head`
   on every start before launching the process (idempotent).
4. `curl https://<host>:8080/healthz` → `{"status":"ok","db":"ok"}`.
5. For webhook mode set `BOT_MODE=webhook`, `WEBHOOK_BASE_URL=https://…` and
   `WEBHOOK_SECRET=<random>`; Telegram updates arrive at
   `POST /telegram/<WEBHOOK_SECRET>`. For polling keep `BOT_MODE=polling`.
6. Back up the PostgreSQL volume (`pgdata`) on a schedule; the wallet ledger and
   order history are the source of truth.

### Admin commands

- `/admin` — verification queue, user search, approve/reject/block/unblock.
- `/products` — categories and product CRUD (price in Toman, stock, photo).
- `/orders` — filter orders by status and change their status.
- `/payments`, `/proofs` — payment log and receipt review.
- `/credit <user_id> <toman> <reason>` — manual wallet adjustment (owner only).
- `/broadcast` — message all verified users.
- `/report` — basic sales figures.
- `/reply <user_id> <text>` — answer a support message.

Current milestone: **complete** — MVP plus fulfillment, extras and hardening
(tag `v1.3.0`).
