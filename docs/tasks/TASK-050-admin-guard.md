# TASK-050 — Admin guard & menu

**Status:** done

## Description
Restrict admin commands to configured Telegram IDs and `owner`/`support` roles.

## Goal
No user outside `ADMIN_IDS` can reach any admin handler or callback.

## Acceptance criteria
- [x] `AdminGuardMiddleware` on all admin router messages/callbacks.
- [x] Roles re-read from settings on every event; support cannot use money commands.
- [x] `/admin` opens the Farsi panel with pending count.
- [x] Non-admins get a Farsi denial and are tested.

## Files affected
`app/bot/middlewares/admin.py`, `app/bot/handlers/admin/__init__.py`, tests.

## Final status
done.
