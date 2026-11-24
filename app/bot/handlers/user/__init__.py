"""Customer handlers."""

from __future__ import annotations

from aiogram import Router

from app.bot.handlers.user import menu, signup, start

router = Router(name="user")
router.include_router(start.router)
router.include_router(signup.router)
router.include_router(menu.router)
