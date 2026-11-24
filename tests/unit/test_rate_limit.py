"""Rate limiter unit tests."""

from __future__ import annotations

from app.bot.middlewares.rate_limit import RateLimiter


def test_window_and_reset() -> None:
    limiter = RateLimiter(limit=2, window=10)
    assert limiter.allow(1, now=0.0)
    assert limiter.allow(1, now=1.0)
    assert not limiter.allow(1, now=2.0)
    assert limiter.allow(1, now=10.0)  # first hit expired
    assert limiter.allow(2, now=10.0)  # different user has a separate bucket


def test_per_user_isolation() -> None:
    limiter = RateLimiter(limit=1, window=60)
    assert limiter.allow(10, now=0.0)
    assert not limiter.allow(10, now=1.0)
    assert limiter.allow(11, now=1.0)
    limiter.reset(10)
    assert limiter.allow(10, now=1.0)
