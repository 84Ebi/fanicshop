"""Global error handler: log and alert admins on critical failures."""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.types import ErrorEvent

from app.config import Settings
from app.i18n import t
from app.logging import get_logger
from app.services.notifications import notify_admins

router = Router(name="errors")
log = get_logger("errors")


@router.errors()
async def on_error(event: ErrorEvent, bot: Bot, settings: Settings) -> None:
    error = event.exception
    log.error("update_failed", error_type=type(error).__name__, error=str(error))
    await notify_admins(bot, settings, t("alert.critical", error=type(error).__name__))
