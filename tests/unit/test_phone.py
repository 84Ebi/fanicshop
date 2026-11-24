"""M2: Iranian mobile normalization (input is Persian/Arabic or ASCII)."""

from __future__ import annotations

import pytest

from app.utils.phone import display_phone, normalize_phone

VALID = [
    ("09121234567", "9121234567"),
    ("9121234567", "9121234567"),
    ("+989121234567", "9121234567"),
    ("00989121234567", "9121234567"),
    ("989121234567", "9121234567"),
    ("0912 123 4567", "9121234567"),
    ("0912-123-4567", "9121234567"),
    ("۰۹۱۲۱۲۳۴۵۶۷", "9121234567"),
    ("٠٩١٢١٢٣٤٥٦٧", "9121234567"),
    ("+98 912 123 4567", "9121234567"),
    ("0098-912-123-4567", "9121234567"),
    (" 09121234567 ", "9121234567"),
]

INVALID = [
    "0912123456",  # 9 digits
    "091212345678",  # 11 digits
    "02188776655",  # landline
    "+12025550123",  # foreign
    "12345",
    "",
    "abc",
    None,
]


@pytest.mark.parametrize(("raw", "expected"), VALID)
def test_normalize_valid(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", INVALID)
def test_normalize_invalid(raw: str | None) -> None:
    assert normalize_phone(raw) is None


def test_display_phone() -> None:
    assert display_phone("9121234567") == "0912 123 4567"
    assert display_phone(None) == ""
