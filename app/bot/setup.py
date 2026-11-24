"""Dispatcher construction: middlewares + routers."""

from __future__ import annotations

from copy import deepcopy

from aiogram import Dispatcher
from aiogram.fsm.storage.base import BaseStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.handlers.admin import build_router as build_admin_router
from app.bot.handlers.errors import router as error_router
from app.bot.handlers.user import build_router as build_user_router
from app.bot.middlewares.db import DbSessionMiddleware
from app.bot.middlewares.rate_limit import RateLimiter, RateLimitMiddleware
from app.bot.middlewares.user import UserMiddleware
from app.bot.storage import make_storage
from app.config import Settings


async def build_dispatcher(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    storage: BaseStorage | None = None,
) -> Dispatcher:
    dp = Dispatcher(storage=storage or await make_storage(settings))
    dp.workflow_data["settings"] = settings
    dp.update.outer_middleware(RateLimitMiddleware(RateLimiter(settings.rate_limit_per_minute)))
    dp.update.outer_middleware(DbSessionMiddleware(session_factory))
    dp.update.outer_middleware(UserMiddleware(settings))
    dp.include_router(build_admin_router())
    dp.include_router(build_user_router())
    dp.include_router(deepcopy(error_router))
    return dp
