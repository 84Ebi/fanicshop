"""Application entrypoint for M0.

Starts an aiohttp server exposing `/healthz` (and, in later milestones, the
internal SMS/internal + Telegram webhook routes). The aiogram dispatcher is
wired in at M2+; this file grows with the bot.
"""

from __future__ import annotations

import asyncio

from aiohttp import web

from app.config import get_settings
from app.logging import get_logger, setup_logging


async def healthz(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/healthz", healthz)
    return app


async def serve_forever() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log = get_logger("main")

    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.http_host, settings.http_port)
    await site.start()
    log.info("http_ready", host=settings.http_host, port=settings.http_port)

    # TODO(M2): start aiogram dispatcher here (polling or webhook).
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


def main() -> None:
    asyncio.run(serve_forever())


if __name__ == "__main__":
    main()
