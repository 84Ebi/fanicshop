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

## M1 — Data layer (pending)
## M2 — Signup & verification (pending)
## M3 — Catalog & cart (pending)
## M4 — Checkout & orders (pending)
## M5 — Payments (pending)
## M6 — Admin panel (pending)
## M7 — Fulfillment (pending)
## M8 — Broadcast & polish (pending)
## M9 — Deploy & hardening (pending)
