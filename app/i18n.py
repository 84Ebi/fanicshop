"""Single-file Persian localization + money/digit rendering.

All user-visible strings live in ``app/locales/fa.json``; code only references
keys. Tests enforce that every referenced key exists and placeholders match.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.utils.digits import fa_digits

LOCALE_PATH = Path(__file__).parent / "locales" / "fa.json"


@lru_cache
def _strings() -> dict[str, str]:
    with LOCALE_PATH.open(encoding="utf-8") as fh:
        data: dict[str, str] = json.load(fh)
    return data


def t(key: str, **kwargs: Any) -> str:
    """Translate a key. Missing placeholders raise (caught by tests)."""
    template = _strings()[key]
    if not kwargs:
        return template
    return template.format(**kwargs)


def has(key: str) -> bool:
    return key in _strings()


def all_keys() -> set[str]:
    return set(_strings())


def money_rial(amount_rial: int) -> str:
    """Render Rial as Persian Toman with Persian digits: ۱۲۳٬۴۵۶ تومان."""
    toman = amount_rial // 10
    grouped = f"{toman:,}".replace(",", "٬")
    return f"{fa_digits(grouped)} تومان"


def amount_toman_latin(amount_rial: int) -> str:
    """Copyable Toman amount with Latin digits (for banking apps)."""
    return f"{amount_rial // 10:,}"


def ltr(value: str) -> str:
    """Wrap a copyable LTR value in RLM so it renders correctly in Persian."""
    return f"\u200f{value}\u200f"
