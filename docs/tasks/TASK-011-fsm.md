# TASK-011 — FSM, middlewares & rate limiting

**Status:** done

## Description
Wire aiogram Dispatcher with Redis FSM (in-memory fallback), DB session injection and per-user rate limits.

## Goal
Stateful conversations survive restarts in production; dev can run without Redis; floods are throttled.

## Acceptance criteria
- [x] `app/bot.py` builds Bot/Dispatcher, registers routers and middleware.
- [x] FSM uses `RedisStorage` when reachable, otherwise `MemoryStorage`.
- [x] DB middleware injects an `AsyncSession` per update and commits/rolls back.
- [x] Rate-limit middleware caps messages/callbacks per user with a Farsi error message.
- [x] Bot commands registered in Persian.

## Files affected
`app/bot.py`, `app/middlewares/`, `app/main.py`, tests.

## Test steps
Unit-test rate limiter; smoke-test bot construction with a dummy token; `/start` on polling.

## Final status
done.
