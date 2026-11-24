"""Admin-only guard. Re-checks the env role map on every event."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.i18n import t

ADMIN_ROLES = ("owner", "support")


class AdminGuardMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if data.get("role") in ADMIN_ROLES:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer(t("admin.denied"), show_alert=True)
        elif isinstance(event, Message):
            await event.answer(t("admin.denied"))
        return None
