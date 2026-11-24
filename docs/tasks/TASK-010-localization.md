# TASK-010 — Localization & helpers

**Status:** in progress

## Description
Single Farsi locale file plus digit/name/phone helpers used by all handlers.

## Goal
No user-facing Persian string in Python code; consistent RTL/money/phone rendering.

## Acceptance criteria
- [ ] `app/locales/fa.json` holds every user-facing string (incl. admin panel).
- [ ] `app/i18n.py`: `t(key, **kwargs)`, `money_rial`, `ltr`, missing-key fails loudly.
- [ ] `app/utils/digits.py`: Persian/Arabic → ASCII on input, Persian digits on output.
- [ ] `app/utils/phone.py`: Iranian mobiles normalized to `9XXXXXXXXX`; rejects landlines/foreign.
- [ ] `app/utils/names.py`: 3–60 Persian-letter names, ZWNJ allowed, digits rejected.
- [ ] Tests for every helper and locale placeholder consistency.

## Files affected
`app/locales/fa.json`, `app/i18n.py`, `app/utils/`, `tests/test_i18n.py`, `tests/test_utils.py`.

## Test steps
`pytest -q` → helper + locale tests green.

## Final status
in progress.
