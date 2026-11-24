# Implementation progress

Log of milestone completion. Each milestone ends with tests green + a demo.

## M0 — Skeleton ✅

**Done**
- `git init` (independent repo in `fanicshop/`), branch `main`.
- uv project, Python 3.12 (`>=3.12,<3.13`), deps pinned (`uv.lock` committed).
- `app/config.py` — pydantic-settings, env-only secrets, comma-parsed admin
  ids/roles, `enable_decoding=False` for list/dict env fields.
- `app/logging.py` — structlog JSON + `mask()` for tokens/PANs.
- `app/main.py` — aiohttp app with `/healthz` (verified `{"status":"ok"}` over
  a real socket).
- `docker-compose.yml` (postgres:16, redis:7, bot) — `docker compose config`
  valid; `Dockerfile` multi-stage, non-root, uv `--frozen`.
- `.env.example` / `.env` (gitignored), `.gitignore`, `README.md`.
- tooling: ruff + mypy clean, pytest 4 passing (config, masking, healthz).

**Environment facts recorded**
- uv system config `/etc/uv/uv.toml` has an unsupported `system-certs` field →
  all uv commands must use `UV_NO_CONFIG=1`. Cache dir pointed at
  `.uv-cache/` (inside workspace) because `~/.cache` is read-only.
- **No Docker daemon / dockerd / Docker Desktop** in this session; podman also
  blocked by the read-only sandbox. `docker compose up` cannot run here →
  will be validated on the deploy VPS (M9). Compose file is syntactically valid.
- Local PostgreSQL **server** binaries exist (`initdb`/`postgres`/`pg_ctl`) —
  integration tests (M1+) can spin a throwaway cluster on localhost without Docker.
- No `redis-server` on host. Redis-dependent code must degrade gracefully
  (in-memory FSM/storage fallback) and be skipped when Redis is absent.

## M1 — Data layer ✅

**Done**
- All ORM models (`users/addresses`, `catalog/cart`, `orders`, `payments`,
  `wallet/audit/broadcast/support/jobs/settings`) with money-safe constraints:
  order total math, stock/reserved bounds, cart qty 1–20, wallet non-negative,
  `UNIQUE(idempotency_key)`, `UNIQUE(bank_code, ref_number)` partial,
  live-intent unique amount + one-live-intent-per-order partial indexes.
- Alembic async setup (`migrations/env.py`), initial migration; verified
  `upgrade → downgrade base → upgrade` clean (26 tables).
- `scripts/seed_demo.py` (idempotent: 3 categories / 6 neutral demo products /
  6 settings) and `scripts/check_ledger.py` (wallet invariant, exit 1 on drift).
- 18 tests green, including real-Postgres constraint tests: double-credit
  guard, expired intent frees its amount, ref-number dedupe, default-address
  partial unique, ledger sum == balance.
- Local test cluster: PostgreSQL 18 at `127.0.0.1:55432` (superuser `fanic`,
  socket `.pgsock/`, data `.pgtest/`). Test DB `fanic_test` is auto-created and
  migrated by `tests/conftest.py`.

## M2 — Signup & verification ✅

**Done**
- Backfilled required docs (PLAN/TASKS/task files/ARCHITECTURE/DATABASE/PAYMENTS/
  DECISIONS/CHANGELOG/legal notes).
- Single Farsi locale (`app/locales/fa.json`) + digit/name/phone/time helpers;
  locale-coverage tests enforce that every referenced key exists and no
  product-specific wording leaks into the engine.
- aiogram dispatcher with Redis FSM (in-memory fallback), per-update DB session,
  user/admin-role injection, admin guard and per-user rate limiting.
- Full signup wizard: 18+ gate → name → contact/manual phone → confirm →
  `pending`. Pending/blocked/rejected users are locked out of the shop.
- Admin panel `/admin`: pending queue, user cards, approve/reject/block/unblock,
  search; signup notifications with inline buttons to admins and the admin group.
- Fake Telegram transport enables end-to-end handler tests without network.
- Fixed `SMS_DEVICE_IDS` parsing, Docker migration/locales paths, env-ified
  Postgres credentials, router reuse across dispatchers and ruff warnings.
- **70 tests green** (unit + real-Postgres integration + end-to-end handler);
  ruff and mypy clean.

## M3 — Catalog & cart ✅

**Done**
- Catalog service: active categories/products, first photo, product cards with
  Farsi description, Toman price and available stock.
- Cart service: price snapshots, qty 1–20 bounded by available stock, add/update/
  remove/clear/subtotal.
- Inline navigation and cart controls; fake-transport end-to-end flow
  (category → product → add → qty → view cart → remove).
- 74 tests green; ruff and mypy clean.
## M4 — Checkout & orders (pending)
## M5 — Payments (pending)
## M6 — Admin panel (pending)
## M7 — Fulfillment (pending)
## M8 — Broadcast & polish (pending)
## M9 — Deploy & hardening (pending)
