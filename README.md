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

## Quick start (any host)

```
# 1. Get the code
git clone git@github.com:84Ebi/fanicshop.git && cd fanicshop

# 2. Configure secrets (token from @BotFather, at minimum)
cp .env.example .env && $EDITOR .env

# 3. Install deps, migrate, run
uv sync --group dev
alembic upgrade head
python -m app.main
```

The bot then:
- starts long-polling Telegram (default `BOT_MODE=polling`), and
- serves `/healthz` (and the internal SMS webhook) on `:8080`.

Check it:

```
curl localhost:8080/healthz    # -> {"status":"ok","db":"ok"}
```

## Running on any system/server

The bot runs anywhere Python 3.12 + PostgreSQL 16 are available — a laptop, a
VPS, or Docker. Pick the path that fits your host.

### Option A — native (uv + system PostgreSQL)

Requires: Python ≥ 3.12, `uv`, and a reachable PostgreSQL 16.

```bash
# 1. Configure environment
cp .env.example .env
$EDITOR .env        # set BOT_TOKEN (required), DATABASE_URL, ADMIN_IDS, …

# 2. Install dependencies
uv sync --group dev

# 3. Create + migrate the database (DATABASE_URL from .env)
alembic upgrade head

# 4. Run (polling + HTTP :8080)
python -m app.main
```

> On some sandboxes `UV_NO_CONFIG=1` is required for `uv` commands.

### Option B — Docker Compose (postgres + redis + bot)

Requires: Docker with Compose v2 and outbound internet to pull images.

```bash
# Secrets: put your real values into .env (docker-compose.yml loads it).
$EDITOR .env

# Build and start the whole stack (postgres, redis, bot).
docker compose up -d --build

# Follow the bot logs.
docker compose logs -f bot
```

The compose stack runs `alembic upgrade head` on startup, so no manual
migration step is needed. The bot is published on `:8080`.

### Keeping it running (production)

For a long-lived process, do not rely on a foreground shell. Use a process
supervisor:

```bash
# systemd unit (example) — see docs/TASK-080-deploy.md for a full walkthrough.
# /etc/systemd/system/fanicbot.service
[Service]
WorkingDirectory=/opt/fanicshop
EnvironmentFile=/opt/fanicshop/.env
ExecStart=/opt/fanicshop/.venv/bin/python -m app.main
Restart=always
```

…or `nohup python -m app.main >> bot.log 2>&1 &`, `supervisord`, or run the
Docker image with `restart: unless-stopped` (already set).

## Using a custom proxy for Telegram

The bot talks to `api.telegram.org`. If your host has no direct route to it
(private network, corporate firewall, restricted egress), route those calls
through a proxy. The bot honors the standard proxy environment variables
(any of `HTTPS_PROXY`, `https_proxy`, `HTTP_PROXY`, `http_proxy`); it reads
them at startup. No extra config file is needed.

```bash
# In .env (or exported before starting):
HTTPS_PROXY=http://127.0.0.1:10808
HTTP_PROXY=http://127.0.0.1:10808

# Also keep local traffic direct:
NO_PROXY=localhost,127.0.0.1
```

The value may be an HTTP, HTTPS, or SOCKS5 proxy (`socks5://…`). aiogram's
proxy support requires the `aiohttp-socks` package, which is already a
dependency of this project (added for this feature).

Verify the proxy works first:

```bash
export HTTPS_PROXY=http://127.0.0.1:10808
curl -sS -I https://api.telegram.org/ | head -1   # expect HTTP/1.1 3xx
```

If `curl` succeeds but the bot still cannot reach Telegram, confirm the proxy
is actually seen by the bot process. The bot reads `HTTPS_PROXY`/`HTTP_PROXY`
both from `.env` and from the exported environment, so either form works;
if you set it nowhere, the bot tries a direct connection and will fail on
hosts without Telegram egress.

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
