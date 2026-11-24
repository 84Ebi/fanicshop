"""Name validation for signup / receiver names.

Persian/Arabic letters, spaces and ZWNJ only; 3–60 chars; digits rejected.
"""

from __future__ import annotations

import re

from app.utils.digits import normalize_digits

_NAME_RE = re.compile(r"^[\u0600-\u06FF\u200c\s]+$")
_WS_RE = re.compile(r"\s+")


def normalize_name(raw: str | None) -> str | None:
    """Return a cleaned name or None if invalid."""
    if not raw:
        return None
    name = normalize_digits(raw).replace("\u200c", "\u200c").strip()
    name = _WS_RE.sub(" ", name)
    if not (3 <= len(name) <= 60):
        return None
    if any(ch.isdigit() for ch in name):
        return None
    if not _NAME_RE.match(name):
        return None
    # At least one letter (not just spaces/ZWNJ).
    if not any("\u0600" <= ch <= "\u06FF" for ch in name):
        return None
    return name
