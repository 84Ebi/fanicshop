"""Customer handlers — router factory (a fresh router per dispatcher)."""

from __future__ import annotations

from copy import deepcopy

from aiogram import Router

from app.bot.handlers.admin.extras import support_router
from app.bot.handlers.user import menu, orders, payments, shop, signup, start


def build_router() -> Router:
    router = Router(name="user")
    for child in (
        start.router,
        signup.router,
        support_router,
        shop.router,
        orders.router,
        payments.router,
        menu.router,
    ):
        router.include_router(deepcopy(child))
    return router
