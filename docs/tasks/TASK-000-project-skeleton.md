# TASK-000 — Project skeleton

**Status:** done (commit `47f4b6f`)

## Description
Bootstrap the repository, toolchain and minimal runnable service.

## Goal
A clean, reproducible Python project with secrets isolated from source and a health endpoint.

## Acceptance criteria
- [x] `git init` on `main`, `.gitignore` excludes `.env`, DB files, caches, venv, logs.
- [x] uv project, Python 3.12, `uv.lock` committed.
- [x] `app/config.py` typed env settings; secrets env-only.
- [x] `app/logging.py` JSON logs + `mask()`.
- [x] `app/main.py` aiohttp `/healthz`.
- [x] Dockerfile + docker-compose (Postgres 16, Redis 7, bot).
- [x] ruff, mypy, pytest green (4 tests).

## Files affected
`pyproject.toml`, `uv.lock`, `.gitignore`, `.env.example`, `Dockerfile`,
`docker-compose.yml`, `app/{__init__,config,logging,main}.py`, `tests/test_smoke.py`,
`docs/progress.md`, `README.md`.

## Implementation notes
`UV_NO_CONFIG=1` is required in this environment (broken system uv config).

## Test steps
`UV_NO_CONFIG=1 uv run pytest` → 4 passed; `curl /healthz` → `{"status":"ok"}`.
