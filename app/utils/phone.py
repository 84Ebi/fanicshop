"""Iranian mobile phone normalization.

Accepted input examples (all normalize to ``9121234567``):
    09121234567, 9121234567, +989121234567, 009891234567,
    989121234567, 0912 123 4567, ۰۹۱۲۱۲۳۴۵۶۷, ٠٩١٢١٢٣٤٥٦٧.

Landlines and foreign numbers are rejected (None).
"""

from __future__ import annotations

import re

from app.utils.digits import normalize_digits

_NON_DIGIT = re.compile(r"[^\d+]")


def normalize_phone(raw: str | None) -> str | None:
    """Return ``9XXXXXXXXX`` (10 digits) or None if not an Iranian mobile."""
    if not raw:
        return None
    s = normalize_digits(raw).strip()
    s = _NON_DIGIT.sub("", s)
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("0098"):
        s = s[4:]
    elif s.startswith("98") and len(s) == 12:
        s = s[2:]
    elif s.startswith("0"):
        s = s[1:]
    if len(s) == 10 and s.isdigit() and s.startswith("9"):
        return s
    return None


def display_phone(phone: str | None) -> str:
    """Human-friendly local form: 0912 123 4567 (ASCII; render with fa_digits)."""
    if not phone or len(phone) != 10:
        return phone or ""
    return f"0{phone[:3]} {phone[3:6]} {phone[6:]}"
