# TASK-007 — Data layer tests

**Status:** todo

## Description
Integration tests against a real temporary PostgreSQL cluster.

## Goal
Prove constraints, relationships and ledger invariants hold under real DB semantics.

## Acceptance criteria
- [ ] Fixture starts/stops throwaway Postgres on a private socket dir.
- [ ] Tests for user status constraints, stock/reserved checks, order math,
      payment uniqueness, wallet ledger.
- [ ] Tests skip cleanly when Postgres binaries are unavailable.

## Files affected
`tests/conftest.py`, `tests/test_db_models.py`, `docs/TASKS.md`.

## Test steps
`UV_NO_CONFIG=1 uv run pytest -q` → all green (integration tests skipped if no Postgres).

## Final status
todo.
