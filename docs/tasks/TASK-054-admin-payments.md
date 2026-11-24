# TASK-054 — Payment log & manual approval

**Status:** done

## Description
Admin payment intent log and receipt approval/rejection.

## Goal
Every payment attempt is visible and can be resolved manually.

## Acceptance criteria
- [x] `/payments` shows recent intents with amounts and statuses.
- [x] `/proofs` lists pending receipts with approve/reject buttons.
- [x] Approval settles the intent; rejection cancels it; customer is notified.
- [x] Tests cover proof attach and both review outcomes.

## Files affected
`app/bot/handlers/admin/payments.py`, `app/services/payments.py`, tests.

## Final status
done.
