"""Outbound Telegram notifications with block detection.

Sending is best-effort: a blocked bot must never fail the business transaction
that triggered the message. Failures are logged; ``bot_blocked_at`` is set when
Telegram says the user blocked us.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import User
from app.i18n import t
from app.logging import get_logger

log = get_logger("notifications")


async def notify_admins(
    bot: Bot,
    settings: Settings,
    text: str,
    *,
    reply_markup: Any | None = None,
) -> int:
    chat_ids: list[int] = list(dict.fromkeys(settings.admin_ids))
    if settings.admin_group_chat_id is not None:
        chat_ids.append(settings.admin_group_chat_id)
    sent = 0
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text, reply_markup=reply_markup)
            sent += 1
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            log.warning("admin_notify_failed", chat_id=chat_id, error=str(exc))
    if not chat_ids:
        log.warning("admin_notify_no_recipients")
    return sent


async def notify_user(bot: Bot, session: AsyncSession, user: User, text: str) -> bool:
    try:
        await bot.send_message(user.telegram_id, text)
        return True
    except TelegramForbiddenError:
        user.bot_blocked_at = datetime.now(UTC)
        await session.flush()
        log.info("user_blocked_bot", user_id=user.id)
        return False
    except TelegramBadRequest as exc:
        log.warning("user_notify_failed", user_id=user.id, error=str(exc))
        return False


async def notify_order_paid(
    bot: Bot,
    settings: Settings,
    order_text: str,
    *,
    reply_markup: Any | None = None,
) -> int:
    """Notify admins that an order is ready to be prepared."""
    return await notify_admins(bot, settings, order_text, reply_markup=reply_markup)


async def notify_signup_admins(
    bot: Bot,
    settings: Settings,
    user: User,
    *,
    reply_markup: Any | None = None,
) -> int:
    text = t(
        "notify.new_signup",
        name=user.full_name,
        phone=user.phone or "-",
        telegram_id=user.telegram_id,
    )
    return await notify_admins(bot, settings, text, reply_markup=reply_markup)
