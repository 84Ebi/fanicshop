"""Application entrypoint: aiogram polling + aiohttp health/SMS/webhook endpoint."""

from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.types import Update
from aiohttp import web
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings, get_settings
from app.db.session import create_engine, create_sessionmaker
from app.logging import get_logger, setup_logging

log = get_logger("main")

SESSION_FACTORY_KEY = web.AppKey("session_factory", async_sessionmaker[AsyncSession])
SETTINGS_KEY = web.AppKey("settings", Settings)
BOT_KEY = web.AppKey("bot", Bot)


async def healthz(request: web.Request) -> web.Response:
    session_factory = request.app.get(SESSION_FACTORY_KEY)
    if session_factory is None:
        return web.json_response({"status": "ok", "db": "not-configured"})
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - health reports, never raises
        return web.json_response({"status": "degraded", "db": str(exc)}, status=503)
    return web.json_response({"status": "ok", "db": "ok"})


def build_app(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    settings: Settings | None = None,
    bot: Bot | None = None,
    dispatcher: object | None = None,
) -> web.Application:
    from app.sms.webhook import sms_webhook

    app = web.Application()
    app.router.add_get("/healthz", healthz)
    if session_factory is not None:
        app[SESSION_FACTORY_KEY] = session_factory
    if settings is not None:
        app[SETTINGS_KEY] = settings
        app.router.add_post("/internal/sms", sms_webhook)
    if bot is not None:
        app[BOT_KEY] = bot
    if dispatcher is not None and settings is not None and settings.webhook_secret:
        app.router.add_post(f"/telegram/{settings.webhook_secret}", _telegram_webhook)
        app["dispatcher"] = dispatcher
    return app


async def _telegram_webhook(request: web.Request) -> web.Response:
    bot: Bot = request.app[BOT_KEY]
    dispatcher = request.app["dispatcher"]
    data = await request.json()
    update = Update.model_validate(data)
    await dispatcher.feed_webhook_update(bot, update)
    return web.Response(text="ok")


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

    app = build_app(session_factory, settings, bot, dispatcher)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.http_host, settings.http_port)
    await site.start()
    log.info("http_ready", host=settings.http_host, port=settings.http_port)

    try:
        if settings.bot_mode == "webhook":
            assert settings.webhook_base_url and settings.webhook_secret
            url = f"{settings.webhook_base_url}/telegram/{settings.webhook_secret}"
            await bot.set_webhook(url=url, secret_token=settings.webhook_secret)
            log.info("webhook_ready", url=url.replace(settings.webhook_secret, "***"))
            await asyncio.Event().wait()
        else:
            await bot.delete_webhook(drop_pending_updates=True)
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
