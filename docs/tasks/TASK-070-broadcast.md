# TASK-070 — Broadcast

**Status:** done

## Description
Admin broadcast to verified users with delivery counts stored in the DB.

## Goal
Send Farsi announcements without leaking unverified or blocked accounts.

## Acceptance criteria
- [x] `/broadcast` collects text, then sends only to `status='verified'` users.
- [x] `broadcasts` and `broadcast_targets` record per-user delivery status.
- [x] Blocked bots are counted, not fatal; admin sees the final sent count.

## Files affected
`app/bot/handlers/admin/extras.py`, `app/bot/states.py`, `app/locales/fa.json`.

## Final status
done.
