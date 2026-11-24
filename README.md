# fanic_bot

A product-agnostic age-restricted shop Telegram bot engine.

**Purpose.** This is the engine for a Telegram-based shop with:
- admin-gated signup (18+ self-declaration),
- catalog / cart / checkout / orders,
- card-to-card payment verification via unique-amount + forwarded bank SMS,
- wallet, admin panel, broadcast, and nightly reconciliation.

**Important.** The codebase is intentionally free of product-specific wording.
Categories, products, welcome text and self-description live in `locales/fa.json`
and the database so the same engine can serve any catalog. Product-agnostic
means it is the seller's responsibility to comply with applicable law
(including any prohibition on online sale of the specific goods) and with the
Telegram Bot ToS. See `docs/legal-notes.fa.md`.

## Stack

- Python 3.12, aiogram 3.34, aiohttp
- PostgreSQL 16 (asyncpg, SQLAlchemy 2 async, Alembic)
- Redis 7 (FSM, rate limits)
- Docker Compose for local + production

## Quickstart

```bash
cp .env.example .env        # then fill in secrets
docker compose up -d --build
curl localhost:8080/healthz
```

Run tests locally:

```bash
uv sync --group dev
uv run pytest
```

## Milestones

See the implementation plan in the session / `docs/`. Current milestone: **M0 skeleton**.
