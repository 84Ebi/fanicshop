"""Load the customer row + admin role for every update."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.services.users import get_by_telegram_id


def _from_user_id(event: TelegramObject) -> int | None:
    inner = event.event if isinstance(event, Update) else event
    from_user = getattr(inner, "from_user", None)
    return getattr(from_user, "id", None)


class UserMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["role"] = None
        data["user"] = None
        tg_id = _from_user_id(event)
        if tg_id is not None:
            data["role"] = self.settings.role_of.get(tg_id)
            session: AsyncSession = data["session"]
            data["user"] = await get_by_telegram_id(session, tg_id)
        return await handler(event, data)
