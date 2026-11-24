# Changelog

## Unreleased

- Next: M3 catalog & cart.

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
