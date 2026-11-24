# TASK-013 — Admin verification

**Status:** todo

## Description
Notify admins on signup; approve/reject/block from notification and panel; notify the user.

## Goal
Verification is fast, auditable and restricted to configured admins.

## Acceptance criteria
- [ ] New signup → admin group/personal notification with Approve/Reject buttons.
- [ ] Buttons work from notification and from admin pending list; stale buttons handled.
- [ ] Approve/reject/block records `user_events` with actor and reason; user is notified.
- [ ] Only `ADMIN_IDS` (owner role for money/settings) can act; others get denied message.
- [ ] Idempotent: double-tap does not duplicate events or messages.

## Files affected
`app/handlers/admin.py`, `app/services/users.py`, `app/notifications.py`, `app/keyboards.py`, tests.

## Test steps
Two test users + one test admin: signup → notification → approve → user notified; double-tap; non-admin denied.

## Final status
todo.
