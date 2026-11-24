# Changelog

## Unreleased

- Docs backfilled after the plan was approved: `PLAN.md`, `TASKS.md`, per-task files,
  `ARCHITECTURE.md`, `DATABASE.md`, `PAYMENTS.md`, `DECISIONS.md`, this changelog.
- M1 data layer models continued: payment and ops schemas, migrations, integration tests.

## v0.1.0-skeleton (2026-11-24)

- Initial `git init` on `main`; `.gitignore`, `.env.example`, README.
- uv/Python 3.12 project with locked dependencies.
- Typed env config, structlog JSON logging with masking.
- aiohttp `/healthz`, Dockerfile, docker-compose (Postgres 16, Redis 7, bot).
- ruff, mypy and pytest wired; 4 smoke tests passing.
- User, catalog and order ORM models started in the working tree.
