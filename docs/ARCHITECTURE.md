# Architecture

## Components

| Component | Responsibility |
| --- | --- |
| `app/main.py` | Process entrypoint. Starts aiohttp (`/healthz`, `/internal/sms`, optional Telegram webhook) and the aiogram dispatcher (polling or webhook). |
| `app/handlers/` | Telegram-facing handlers. Validate input, call services, render locale strings. No DB transactions here. |
| `app/services/` | Business rules and units of work: signup, orders, payments, wallet, fulfillment, admin. Own transactions and locking. |
| `app/repositories/` | Reusable SQLAlchemy queries. |
| `app/db/models/` | Declarative schema (SQLAlchemy 2). All money BIGINT Rial. |
| `app/db/session.py` | Async engine/session factory and `session_scope`. |
| `app/sms/` | HMAC verification, Iranian bank SMS parsers, amount extraction. |
| `app/locales/fa.json` | Every user-facing string, including admin panel copy. |
| `app/notifications.py` | Sends messages to users/admins; single place for outbound formatting. |
| `migrations/` | Alembic revisions. |
| `docs/` | Plans, tasks, decisions, schema, payments, changelog. |

## Data flow

```
update → aiogram Dispatcher → FSM middleware (Redis/in-memory)
       → handler → service (BEGIN) → repository → Postgres (COMMIT)
                        ├─→ notifier → Telegram user / admin group
                        └─→ event row (audit/history)

POST /internal/sms → HMAC + device check → sms parse → match intent (row lock)
                  → bank_transaction + wallet/order update + notifications
```

## Folder structure

```
fanicshop/
├── app/
│   ├── db/{base.py, session.py, models/}
│   ├── handlers/          # user.py, shop.py, payments.py, admin.py
│   ├── services/          # users.py, catalog.py, orders.py, payments.py, wallet.py, admin.py
│   ├── repositories/
│   ├── sms/
│   ├── locales/fa.json
│   ├── config.py, logging.py, notifications.py, main.py
├── migrations/            # Alembic env.py + versions/
├── tests/
├── docs/                  # this folder
├── Dockerfile, docker-compose.yml, pyproject.toml, uv.lock, .env.example
└── README.md
```

## Key design decisions

1. **Rial integers everywhere** — no floats, no decimal rounding bugs; display divides by 10.
2. **Unique amount suffix** — card-to-card has no API; a unique Rial tail lets automated SMS
   parsing match a transfer to one intent. Receipt upload is the human fallback.
3. **Full PAN never stored** — only in env; DB holds masked last-4 for display.
4. **Append-only ledgers** — `wallet_transactions`, `user_events`, `order_status_history`,
   `admin_audit_log`, `bank_transactions` are never UPDATEd.
5. **Transaction + row lock for matching** — prevents two intents claiming the same transfer.
6. **Roles** — `owner` vs `support`; money/broadcast/settings restricted to owner.
7. **Product-agnostic engine** — all product wording comes from locale/DB, not code.
8. **Long polling default** — no public HTTPS endpoint required for MVP; webhook supported for
   the SMS callback and Telegram via the same aiohttp app in production.
