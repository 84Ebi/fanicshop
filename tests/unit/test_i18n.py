"""M2: single-file localization integrity + money rendering."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.i18n import LOCALE_PATH, all_keys, amount_toman_latin, money_rial, t
from app.utils.digits import fa_digits, to_ascii_digits

APP_DIR = Path(__file__).resolve().parents[2] / "app"
T_KEY = re.compile(r'\bt\(\s*"([^"]+)"')
FORBIDDEN = ("تنباکو", "سیگار", "قلیان", "tobacco", "cigarette")


def _load_raw() -> dict[str, str]:
    duplicates: list[str] = []

    def hook(pairs):
        seen = set()
        for key, _ in pairs:
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        return dict(pairs)

    data = json.loads(LOCALE_PATH.read_text(encoding="utf-8"), object_pairs_hook=hook)
    assert duplicates == [], f"duplicate locale keys: {duplicates}"
    return data


def test_locale_is_valid_json() -> None:
    data = _load_raw()
    assert data
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in data.items())


def test_every_referenced_key_exists() -> None:
    referenced: set[str] = set()
    for path in APP_DIR.rglob("*.py"):
        referenced.update(T_KEY.findall(path.read_text(encoding="utf-8")))
    missing = referenced - all_keys()
    assert missing == set(), f"missing locale keys: {sorted(missing)}"


def test_dynamic_status_keys_exist() -> None:
    for status in ("draft", "pending", "verified", "rejected", "blocked"):
        assert f"profile.status.{status}" in all_keys()


def test_placeholders_present() -> None:
    assert "{" in t("signup.confirm_title")
    assert "{" in t("admin.user_card")
    assert "{" in t("notify.new_signup")
    assert t("common.yes") == "✅ بله"


def test_no_product_specific_wording() -> None:
    text = LOCALE_PATH.read_text(encoding="utf-8").lower()
    for token in FORBIDDEN:
        assert token.lower() not in text


def test_money_and_digits() -> None:
    assert fa_digits("0912") == "۰۹۱۲"
    assert to_ascii_digits("۰۹۱۲") == "0912"
    assert money_rial(1_234_560) == "۱۲۳٬۴۵۶ تومان"
    assert amount_toman_latin(1_234_560) == "123,456"


def test_missing_key_raises() -> None:
    with pytest.raises(KeyError):
        t("does.not.exist")
