# TASK-051 — Admin user management

**Status:** done

## Description
Pending queue, user cards, approve/reject/block/unblock and search.

## Goal
Admins can verify and moderate users from inside the bot.

## Acceptance criteria
- [x] `/admin` pending list with pagination; approve/reject/block/unblock buttons.
- [x] Search by id, phone or name; reasons stored and reported to the user.
- [x] Every action appends `user_events` and `admin_audit_log`.
- [x] End-to-end approval and non-admin denial tests.

## Files affected
`app/bot/handlers/admin/users.py`, `app/services/users.py`, `app/services/audit.py`, tests.

## Final status
done.
