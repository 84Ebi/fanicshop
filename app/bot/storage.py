"""FSM storage: Redis when reachable, in-memory fallback otherwise."""

from __future__ import annotations

from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from app.config import Settings
from app.logging import get_logger

log = get_logger("storage")


async def make_storage(settings: Settings) -> BaseStorage:
    if settings.redis_url:
        storage: RedisStorage | None = None
        try:
            storage = RedisStorage.from_url(settings.redis_url)
            await storage.redis.ping()
            log.info("fsm_storage_redis")
            return storage
        except Exception as exc:  # noqa: BLE001 - any redis failure is non-fatal
            log.warning("redis_unavailable_fallback_memory", error=str(exc))
            if storage is not None:
                try:
                    await storage.redis.aclose()
                except Exception:  # noqa: BLE001
                    pass
    return MemoryStorage()
