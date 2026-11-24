"""Bank SMS parser and masking tests."""

from __future__ import annotations

from app.sms.parser import mask_sms, parse_sms


def test_parses_persian_transfer() -> None:
    text = (
        "بانک ملی: مبلغ ۱۲۳,۴۵۶ ریال به کارت 6037991234567890 واریز شد. "
        "کد رهگیری ۱۲۳۴۵۶۷۸۹."
    )
    parsed = parse_sms(text)
    assert parsed is not None
    assert parsed.amount_rial == 123456
    assert parsed.ref_number == "123456789"
    assert parsed.bank_code == "melli"
    assert parsed.dest_card_last4 == "7890"


def test_parses_toman_and_reference() -> None:
    parsed = parse_sms("مبلغ: 12,000 تومان - ref AB12345")
    assert parsed is not None
    assert parsed.amount_rial == 120_000
    assert parsed.ref_number == "AB12345"


def test_ignores_non_transfer_sms() -> None:
    assert parse_sms("سلام چطوری؟") is None
    assert parse_sms("برق رفت") is None


def test_masking() -> None:
    masked = mask_sms("کارت 6037991234567890 و شماره 09121234567")
    assert "6037991234567890" not in masked
    assert "09121234567" not in masked
    assert "[PAN]" in masked and "[PHONE]" in masked
