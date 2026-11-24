"""Application entrypoint: aiogram polling + aiohttp health endpoint.

The worker process (M5+) will share the same image and database. Webhook mode
is added in M9; the MVP runs long polling so no TLS/domain is required.
"""

from __future__ import annotations

import asyncio

from aiogram import Bot
from aiohttp import web
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings, get_settings
from app.db.session import create_engine, create_sessionmaker
from app.logging import get_logger, setup_logging

log = get_logger("main")

SESSION_FACTORY_KEY = web.AppKey("session_factory", async_sessionmaker[AsyncSession])


async def healthz(request: web.Request) -> web.Response:
    session_factory = request.app.get(SESSION_FACTORY_KEY)
    if session_factory is None:
        return web.json_response({"status": "ok", "db": "not-configured"})
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - health endpoint reports, never raises
        return web.json_response({"status": "degraded", "db": str(exc)}, status=503)
    return web.json_response({"status": "ok", "db": "ok"})


def build_app(session_factory: async_sessionmaker[AsyncSession] | None = None) -> web.Application:
    app = web.Application()
    app.router.add_get("/healthz", healthz)
    # Tests that only exercise routing can still call /healthz unconfigured.
    if session_factory is not None:
        app[SESSION_FACTORY_KEY] = session_factory
    return app


async def serve_forever(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    engine = create_engine(settings)
    session_factory = create_sessionmaker(engine)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    log.info("db_ready")

    bot = Bot(token=settings.bot_token)
    dispatcher = await build_dispatcher(settings, session_factory)

    app = build_app(session_factory)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.http_host, settings.http_port)
    await site.start()
    log.info("http_ready", host=settings.http_host, port=settings.http_port)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()
        await engine.dispose()
        log.info("shutdown_complete")


def main() -> None:
    asyncio.run(serve_forever())


if __name__ == "__main__":
    main()
