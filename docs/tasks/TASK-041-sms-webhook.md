# TASK-041 — SMS ingestion

**Status:** done

## Description
HMAC-protected internal webhook for forwarded bank SMS, with parser and masking.

## Goal
Automatic payment signals arrive without exposing PANs, phones or the HMAC secret.

## Acceptance criteria
- [x] `POST /internal/sms` checks HMAC-SHA256 signature and device allow-list.
- [x] Raw hash deduplication; raw body stored masked and only when enabled.
- [x] Persian/English amount, reference, bank and card-last4 parsing.
- [x] Integration tests: bad signature, match, duplicate SMS.

## Files affected
`app/sms/`, `app/main.py`, `app/config.py`, tests.

## Test steps
`pytest -q`; post signed SMS → `matched`, repeat → `duplicate-sms`, unsigned → 401.

## Final status
done.
