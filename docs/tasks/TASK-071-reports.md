# TASK-071 — Reports & support

**Status:** done

## Description
Basic sales report and a customer support channel with admin replies.

## Goal
Admins get quick revenue/order counts; customers can reach support in Farsi.

## Acceptance criteria
- [x] `/report` shows total orders, paid orders and paid revenue in Toman.
- [x] Support menu collects a message and notifies admins; `/reply <id> <text>` answers.
- [x] All strings in the locale file.

## Files affected
`app/bot/handlers/admin/extras.py`, `app/locales/fa.json`.

## Final status
done.
