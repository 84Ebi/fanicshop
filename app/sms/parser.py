"""Heuristic parser for Iranian bank transfer SMS messages.

Banks use many wording variants; we extract only what we need (amount, reference,
destination card last4) and never store unmasked PANs or sender numbers.
"""

from __future__ import annotations

import re

from app.services.payments import ParsedSms
from app.utils.digits import to_ascii_digits

_AMOUNT_FA = re.compile(r"(?:مبلغ|مقدار)\s*:?\s*([\d,]+)\s*(ریال|تومان)?", re.I)
_AMOUNT_EN = re.compile(r"amount\s*:?\s*([\d,]+)\s*(rial|toman)?", re.I)
_REF_FA = re.compile(r"(?:کد رهگیری|شماره پیگیری|کد پیگیری)\s*:?\s*([A-Za-z0-9]+)")
_REF_EN = re.compile(r"(?:ref(?:erence)?|trace)\s*:?\s*([A-Za-z0-9]+)", re.I)
_CARD = re.compile(r"\b(?:\d[ -]?){12,15}(\d{4})\b")
_PAN = re.compile(r"\b(?:\d[ -]?){13,18}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+98|0098|0)?9\d{9}(?!\d)")

_BANKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("melli", ("بانک ملی", "ملی", "melli")),
    ("mellat", ("بانک ملت", "ملت", "mellat")),
    ("tejarat", ("بانک تجارت", "تجارت", "tejarat")),
    ("pasargad", ("پاسارگاد", "pasargad")),
    ("iranzamin", ("بانک ایرانزمین", "ایرانزمین")),
    ("saderat", ("بانک صادرات", "صادرات", "saderat")),
    ("sepah", ("بانک سپه", "سپه", "sepah")),
    ("maskan", ("بانک مسکن", "مسکن", "maskan")),
)


def mask_sms(text: str) -> str:
    """Mask long number runs and mobile numbers in a stored SMS body."""
    out = _PAN.sub("[PAN]", text)
    return _PHONE.sub("[PHONE]", out)


def parse_sms(text: str) -> ParsedSms | None:
    """Return parsed transfer details, or None when the SMS is not a transfer."""
    if not text or "ریال" not in text and "تومان" not in text and "rial" not in text.lower():
        return None
    text = to_ascii_digits(text)

    amount = 0
    multiplier = 1
    for pattern in (_AMOUNT_FA, _AMOUNT_EN):
        match = pattern.search(text)
        if match:
            amount = int(match.group(1).replace(",", ""))
            unit = (match.group(2) or "").lower()
            multiplier = 10 if unit in ("تومان", "toman") else 1
            break
    if amount <= 0:
        return None

    ref: str | None = None
    for pattern in (_REF_FA, _REF_EN):
        match = pattern.search(text)
        if match:
            ref = match.group(1)[:64]
            break

    card_match = _CARD.search(text)
    last4 = card_match.group(1) if card_match else None
    bank = "unknown"
    lowered = text.lower()
    for code, keywords in _BANKS:
        if any(keyword in lowered for keyword in keywords):
            bank = code
            break

    return ParsedSms(
        amount_rial=amount * multiplier,
        ref_number=ref,
        bank_code=bank,
        dest_card_last4=last4,
    )
