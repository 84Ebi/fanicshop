# TASK-081 — Monitoring

**Status:** done

## Description
Health endpoint and structured logs with admin alerts on failures.

## Goal
Operators can detect database or payment-ingestion problems quickly.

## Acceptance criteria
- [x] `/healthz` checks a real DB query and returns 503 on failure.
- [x] JSON structlog with masking of PANs/token-like strings.
- [x] Global error handler notifies admins; unmatched/ambiguous SMS alerts admins.
- [x] `scripts/check_ledger.py` verifies wallet invariant for scheduled checks.

## Files affected
`app/main.py`, `app/logging.py`, `app/bot/handlers/errors.py`, `scripts/check_ledger.py`.

## Final status
done.
