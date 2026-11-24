"""Customer handlers — router factory (a fresh router per dispatcher)."""

from __future__ import annotations

from copy import deepcopy

from aiogram import Router

from app.bot.handlers.user import menu, signup, start


def build_router() -> Router:
    router = Router(name="user")
    for child in (start.router, signup.router, menu.router):
        router.include_router(deepcopy(child))
    return router
