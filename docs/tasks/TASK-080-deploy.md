# TASK-080 — Deployment docs

**Status:** done

## Description
Docker entrypoint that migrates on startup, VPS setup and polling/webhook switch.

## Goal
Deploying a fresh instance is a short, repeatable procedure.

## Acceptance criteria
- [x] `scripts/entrypoint.sh` runs `alembic upgrade head` then `python -m app.main`.
- [x] Dockerfile copies migrations and entrypoint; runs as non-root.
- [x] README documents env, VPS setup, healthcheck and webhook/polling modes.
- [x] PostgreSQL volume backup note.

## Files affected
`Dockerfile`, `scripts/entrypoint.sh`, `README.md`, `docker-compose.yml`.

## Final status
done.
