# TASK-043 — Receipt fallback

**Status:** done

## Description
Photo receipt upload with admin approval/rejection when automatic matching fails.

## Goal
Payments never depend solely on SMS forwarding.

## Acceptance criteria
- [x] Customer uploads a photo → `PaymentProof` pending, intent `awaiting_review`.
- [x] Admin `/proofs` lists pending receipts with approve/reject buttons.
- [x] Approval settles the intent; rejection cancels it; customer is notified.
- [x] Only Telegram `file_id` is stored, never image bytes.

## Files affected
`app/bot/handlers/user/payments.py`, `app/bot/handlers/admin/payments.py`,
`app/services/payments.py`, tests.

## Test steps
`pytest -q`; attach proof → review approve/reject → ledger/order assertions.

## Final status
done.
