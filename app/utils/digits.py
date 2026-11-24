"""Digit normalization and Persian number rendering.

Persian/Arabic-Indic digits are accepted on input and rendered on output.
Internal storage is always ASCII (phones, amounts, codes).
"""

from __future__ import annotations

_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ASCII = "0123456789"

_TO_ASCII = str.maketrans(
    {
        **dict(zip(_FA_DIGITS, _ASCII, strict=False)),
        **dict(zip(_AR_DIGITS, _ASCII, strict=False)),
    }
)
_TO_FA = str.maketrans(dict(zip(_ASCII, _FA_DIGITS, strict=False)))


def to_ascii_digits(value: str) -> str:
    """Convert ۰-۹ and ٠-٩ to 0-9, leaving everything else intact."""
    return value.translate(_TO_ASCII)


def fa_digits(value: str | int) -> str:
    """Render ASCII digits as Persian digits."""
    return str(value).translate(_TO_FA)


def normalize_digits(value: str) -> str:
    """Alias used by input parsers: Persian/Arabic digits → ASCII."""
    return to_ascii_digits(value)
