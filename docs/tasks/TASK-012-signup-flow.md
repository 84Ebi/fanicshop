# TASK-012 — Signup flow

**Status:** todo

## Description
Mandatory 18+ gate, full name, phone (contact button + manual fallback), confirmation, pending state.

## Goal
No unverified user reaches the shop; every signup is auditable.

## Acceptance criteria
- [ ] `/start` shows welcome + age question; "no" → denied message, no further steps.
- [ ] Name validated (TASK-010); phone via contact button or manual input, both validated.
- [ ] Wrong contact (someone else's number) is rejected.
- [ ] Confirmation step allows editing; submit creates `pending` user + `user_events`.
- [ ] Pending/blocked/rejected users get the right Farsi message and no shop menu.
- [ ] Repeat `/start` resumes correctly without duplicate users.

## Files affected
`app/handlers/signup.py`, `app/services/users.py`, `app/keyboards.py`, `app/states.py`, tests.

## Test steps
Run bot with a test user: complete signup, verify DB row/events; repeat /start; try blocked user.

## Final status
todo.
