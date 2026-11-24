"""M2: name validation."""

from __future__ import annotations

import pytest

from app.utils.names import normalize_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("علی رضایی", "علی رضایی"),
        ("زهرا", "زهرا"),
        ("محمد مهدی", "محمد مهدی"),
        ("علی‌رضا", "علی‌رضا"),
        ("  علی   رضایی  ", "علی رضایی"),
    ],
)
def test_valid_names(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "123",
        "علی1",
        "ab",
        "   ",
        "John Smith",
        "ع" * 61,
        None,
        "",
    ],
)
def test_invalid_names(raw: str | None) -> None:
    assert normalize_name(raw) is None
