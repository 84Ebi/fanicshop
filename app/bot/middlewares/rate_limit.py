"""Simple per-user sliding-window rate limit.

In-memory by design: the bot is single-process, and a restart clearing counters
is acceptable. Redis-backed limits can be added later without changing callers.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.i18n import t
from app.logging import get_logger

log = get_logger("rate_limit")


def _user_id(event: TelegramObject) -> int | None:
    inner = event.event if isinstance(event, Update) else event
    from_user = getattr(inner, "from_user", None)
    return getattr(from_user, "id", None)


class RateLimiter:
    """Fixed-window counter: at most `limit` events per `window` seconds."""

    def __init__(self, limit: int = 20, window: float = 60.0) -> None:
        self.limit = max(1, limit)
        self.window = window
        self._hits: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        bucket = self._hits[user_id]
        while bucket and current - bucket[0] >= self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(current)
        return True

    def reset(self, user_id: int | None = None) -> None:
        if user_id is None:
            self._hits.clear()
        else:
            self._hits.pop(user_id, None)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limiter: RateLimiter) -> None:
        self.limiter = limiter

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = _user_id(event)
        if user_id is not None and not self.limiter.allow(user_id):
            log.warning("rate_limited", telegram_id=user_id)
            text = t("error.rate_limit")
            if hasattr(event, "answer"):
                await event.answer(text)
            elif hasattr(event, "message") and event.message is not None:
                await event.message.answer(text)
            return None
        return await handler(event, data)
