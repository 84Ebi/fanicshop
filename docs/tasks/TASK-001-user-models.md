# TASK-001 — User & address models

**Status:** done

## Description
Model identity, verification lifecycle, audit events and shipping addresses.

## Goal
Users can be `draft → pending → verified/rejected`, blocked, and have auditable status changes.

## Acceptance criteria
- [x] `User` with unique `telegram_id`, 18+ timestamp, phone, status, wallet balance, block flags.
- [x] `UserEvent` append-only audit with actor and reason.
- [x] `Address` snapshot-friendly fields, default-address partial unique index, soft delete.
- [x] CHECK constraints for status/event validity and non-negative balance.

## Files affected
`app/db/models/users.py`, `app/db/base.py`.

## Implementation notes
Phone kept as 10-digit Iranian national number (`9xxxxxxxxx`); +98 shown to users only.

## Test steps
Import models; create in a real Postgres test DB; assert constraints reject bad status/negative balance.

## Final status
done — implemented in working tree, verified with M1 model tests.
