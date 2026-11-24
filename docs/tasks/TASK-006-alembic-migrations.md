# TASK-006 — Alembic migrations

**Status:** todo

## Description
Set up Alembic async environment and generate the initial schema revision.

## Goal
Schema is versioned and can be upgraded/downgraded reproducibly on PostgreSQL.

## Acceptance criteria
- [ ] `alembic.ini`, `migrations/env.py` with async engine and `Base.metadata`.
- [ ] Initial revision creates all tables/constraints/indexes.
- [ ] `alembic upgrade head` and `downgrade base` both succeed on a clean DB.
- [ ] Docker image copies and can run migrations.

## Files affected
`alembic.ini`, `migrations/`, `Dockerfile`, `docs/DATABASE.md`.

## Test steps
Spin throwaway local Postgres, run upgrade head, inspect tables, run downgrade base.

## Final status
todo.
