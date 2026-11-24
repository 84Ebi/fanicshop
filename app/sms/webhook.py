"""HMAC-protected internal endpoint that receives forwarded bank SMS."""

from __future__ import annotations

import hashlib
import hmac
import json

from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.i18n import t
from app.logging import get_logger
from app.main import BOT_KEY, SESSION_FACTORY_KEY, SETTINGS_KEY
from app.services.notifications import notify_admins
from app.services.payments import match_sms
from app.sms.parser import mask_sms, parse_sms

log = get_logger("sms_webhook")


async def sms_webhook(request: web.Request) -> web.Response:
    settings: Settings = request.app[SETTINGS_KEY]
    factory: async_sessionmaker[AsyncSession] | None = request.app.get(SESSION_FACTORY_KEY)
    if factory is None:
        return web.json_response({"ok": False, "error": "not-configured"}, status=503)

    body = await request.read()
    device = request.headers.get("X-SMS-Device-Id", "")
    signature = request.headers.get("X-SMS-Signature", "")
    if not settings.sms_hmac_secret or not signature:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)
    expected = hmac.new(settings.sms_hmac_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return web.json_response({"ok": False, "error": "bad-signature"}, status=401)
    if device not in settings.sms_device_ids:
        return web.json_response({"ok": False, "error": "unknown-device"}, status=403)

    try:
        payload = json.loads(body)
        raw_text = str(payload["body"])
    except (ValueError, KeyError, TypeError):
        return web.json_response({"ok": False, "error": "bad-payload"}, status=400)

    raw_hash = hashlib.sha256(raw_text.encode()).hexdigest()
    from sqlalchemy import select

    from app.db.models import SmsMessage

    async with factory() as session:
        duplicate = await session.scalar(
            select(SmsMessage).where(SmsMessage.raw_hash == raw_hash)
        )
        if duplicate is not None:
            return web.json_response({"ok": True, "outcome": "duplicate-sms"})
        sms = SmsMessage(
            source="sms_forwarder",
            raw_text=mask_sms(raw_text) if settings.store_raw_sms else "",
            raw_hash=raw_hash,
            device_id=device,
            remote_ip=request.remote or "",
            parse_status="unparsed",
        )
        session.add(sms)
        await session.flush()
        parsed = parse_sms(raw_text)
        outcome = "unparsed"
        if parsed is not None:
            outcome = await match_sms(session, parsed, sms)
        await session.commit()

    if outcome in ("ambiguous", "unmatched", "duplicate"):

        bot = request.app.get(BOT_KEY)
        if bot is not None:
            await notify_admins(
                bot,
                settings,
                t(
                    "pay.sms_alert",
                    outcome=outcome,
                    amount=str(parsed.amount_rial) if parsed else "-",
                ),
            )
    return web.json_response({"ok": True, "outcome": outcome})
