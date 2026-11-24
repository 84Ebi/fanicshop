# TASK-072 — Hardening pass

**Status:** done

## Description
Rate limiting, input validation and admin alerts on critical failures.

## Goal
Malformed input or a flood cannot break the bot; failures are visible to admins.

## Acceptance criteria
- [x] Per-user rate limiter (30 updates/min, configurable) with Farsi error.
- [x] Persian/Arabic digit normalization and Iranian phone/name validation.
- [x] Unique idempotency keys on wallet rows; DB CHECK constraints on money/status.
- [x] Global aiogram error handler logs and alerts admins.

## Files affected
`app/bot/middlewares/rate_limit.py`, `app/bot/handlers/errors.py`, `app/utils/`, tests.

## Final status
done.
