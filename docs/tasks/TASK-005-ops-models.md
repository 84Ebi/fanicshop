# TASK-005 — Ops models

**Status:** todo

## Description
Wallet ledger, admin audit log, broadcast, support threads and misc runtime tables.

## Goal
Money movements and administrative actions are append-only and explainable.

## Acceptance criteria
- [ ] `WalletTransaction`: user_id, delta_rial signed, balance_after_rial, type, reason, ref, actor.
- [ ] `AdminAuditLog`: actor, action, target, payload JSON, created_at.
- [ ] `Broadcast`: text/media, creator, status, counts; `BroadcastTarget` per recipient delivery state.
- [ ] `SupportThread`/`SupportMessage` for user-admin conversation.
- [ ] `Job` for deferred work; `Setting` for runtime key/value config.

## Files affected
`app/db/models/ops.py`, `app/db/models/__init__.py`.

## Test steps
Insert ledger rows and assert balance_after arithmetic; insert broadcast and targets.

## Final status
todo.
