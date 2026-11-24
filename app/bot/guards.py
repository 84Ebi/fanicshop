"""Shared access guard for shopping features."""

from __future__ import annotations

from aiogram.types import CallbackQuery, Message

from app.db.models import User
from app.i18n import t
from app.services.users import can_access_shop


async def _reason_text(user: User | None) -> str | None:
    if user is None:
        return t("common.start_hint")
    status = getattr(user, "status", None)
    if status == "pending":
        return t("start.pending")
    if status == "blocked":
        return t("start.blocked", reason=getattr(user, "block_reason", None) or t("common.unknown"))
    if status == "rejected":
        reason = getattr(user, "rejection_reason", None) or t("common.unknown")
        return t("start.rejected", reason=reason)
    return t("common.start_hint")


async def allow_message(message: Message, user: User | None) -> bool:
    if can_access_shop(user):
        return True
    await message.answer(await _reason_text(user) or t("common.start_hint"))
    return False


async def allow_callback(callback: CallbackQuery, user: User | None) -> bool:
    if can_access_shop(user):
        return True
    text = await _reason_text(user) or t("common.start_hint")
    if callback.message is not None:
        await callback.message.answer(text)
    else:
        await callback.answer(text, show_alert=True)
    await callback.answer()
    return False
