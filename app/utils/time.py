"""Tehran-time rendering helpers (storage stays UTC)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.utils.digits import fa_digits

TEHRAN = ZoneInfo("Asia/Tehran")


def tehran_now() -> datetime:
    return datetime.now(TEHRAN)


def format_dt(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    local = dt.astimezone(TEHRAN) if dt.tzinfo else dt.replace(tzinfo=TEHRAN)
    return fa_digits(local.strftime("%Y-%m-%d %H:%M"))
