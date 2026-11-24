"""Admin handlers."""

from __future__ import annotations

from aiogram import Router

from app.bot.handlers.admin import users

router = Router(name="admin")
router.include_router(users.router)
