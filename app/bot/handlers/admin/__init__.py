"""Admin handlers — router factory (a fresh router per dispatcher)."""

from __future__ import annotations

from copy import deepcopy

from aiogram import Router

from app.bot.handlers.admin import extras, payments, shop, users
from app.bot.middlewares.admin import AdminGuardMiddleware


def build_router() -> Router:
    router = Router(name="admin")
    router.message.middleware(AdminGuardMiddleware())
    router.callback_query.middleware(AdminGuardMiddleware())
    # Handler modules expose module-level routers; copy them so multiple
    # dispatchers (tests, webhook + polling) can coexist in one process.
    router.include_router(deepcopy(users.router))
    router.include_router(deepcopy(payments.router))
    router.include_router(deepcopy(shop.router))
    router.include_router(deepcopy(extras.admin_router))
    return router
