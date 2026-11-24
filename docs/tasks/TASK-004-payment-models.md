# TASK-004 — Payment models

**Status:** in progress

## Description
Payment intents, forwarded SMS messages, parsed bank transactions, shop cards, receipts and card bindings.

## Goal
Every card-to-card transfer attempt is uniquely identifiable, auditable and matchable.

## Acceptance criteria
- [ ] `PaymentIntent`: user_id, optional order_id, target_rial, unique suffix_rial, amount_due_rial,
      expires_at, status (pending/matched/expired/failed/cancelled), paid_rial, intent_code.
- [ ] `SmsMessage`: device_id, HMAC verified, raw body optional (masked), received_at, parse state.
- [ ] `BankTransaction`: amount_rial, reference, sender info masked, sms_id, matched_intent_id,
      unique reference to stop duplicate matching.
- [ ] `ShopCard`: label, masked PAN, holder, bank, active — full PAN only in env, never in DB.
- [ ] `PaymentProof`: photo file_id, status pending/approved/rejected, reviewer, note.
- [ ] `CardBinding`: optional remembered last4 for repeat customers.
- [ ] Unique/partial indexes + CHECK constraints for money and states.

## Files affected
`app/db/models/payments.py`, `app/db/models/__init__.py`.

## Implementation notes
Full PAN and HMAC secret stay in env. `amount_due_rial` carries the unique suffix; matching uses
`amount_due_rial` and an unmatched-intent lock inside a transaction.

## Test steps
Create intent + SMS + bank transaction; assert unique reference prevents a second match; assert
states enumerated correctly.

## Final status
in progress.
