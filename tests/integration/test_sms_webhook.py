"""HMAC SMS webhook: signature, dedupe and automatic payment match."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db.models import Category, PaymentIntent, Product, SmsMessage, User
from app.main import build_app
from app.services.payments import create_intent
from app.services.wallet import credit

SECRET = "test-sms-secret"
DEVICE = "dev-1"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        bot_token="123456:TEST",
        sms_hmac_secret=SECRET,
        sms_device_ids=DEVICE,
        store_raw_sms=True,
    )


@pytest.fixture
async def webhook_env(engine):
    from tests.conftest import truncate_all

    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = build_app(factory, _settings())
    yield app, factory
    await truncate_all(engine)


def _post(app, body: dict, *, device: str = DEVICE, sign: bool = True):
    payload = json.dumps(body).encode()
    signature = hmac.new(SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return app, {
        "data": payload,
        "headers": {
            "Content-Type": "application/json",
            "X-SMS-Device-Id": device,
            "X-SMS-Signature": signature if sign else "bad",
        },
    }


async def test_webhook_rejects_bad_signature(webhook_env, aiohttp_client) -> None:
    app, _ = webhook_env
    client = await aiohttp_client(app)
    _, kwargs = _post(app, {"body": "test"}, sign=False)
    response = await client.post("/internal/sms", **kwargs)
    assert response.status == 401


async def test_webhook_matches_intent_and_dedupes(webhook_env, aiohttp_client) -> None:
    app, factory = webhook_env
    client = await aiohttp_client(app)
    async with factory() as session:
        tag = secrets.token_hex(4)
        category = Category(slug=f"sms-{tag}", title_fa="چای")
        product = Product(
            category=category,
            title_fa="چای",
            price_rial=100_000,
            stock_qty=5,
            reserved_qty=0,
        )
        user = User(
            telegram_id=secrets.randbelow(10**9),
            full_name="علی رضایی",
            status="verified",
            phone=f"9{secrets.randbelow(10**9):09d}",
        )
        session.add_all([product, user])
        await session.flush()
        await credit(
            session,
            user_id=user.id,
            amount_rial=10_000,
            tx_type="topup",
            idempotency_key=f"seed:{tag}",
            reason="seed",
        )
        intent = await create_intent(
            session,
            user_id=user.id,
            amount_rial=50_000,
            purpose="wallet_topup",
            settings=_settings(),
        )
        await session.commit()
        amount, user_id, intent_id = intent.expected_amount_rial, user.id, intent.id

    body = {
        "body": (
            f"بانک ملی: مبلغ {amount} ریال به کارت 6037991234567890 "
            "واریز شد. کد رهگیری 999888777."
        ),
    }
    _, kwargs = _post(app, body)
    response = await client.post("/internal/sms", **kwargs)
    assert response.status == 200
    assert (await response.json())["outcome"] == "matched"

    async with factory() as session:
        refreshed = await session.get(PaymentIntent, intent_id)
        assert refreshed is not None and refreshed.status == "matched"
        user_row = await session.get(User, user_id)
        assert user_row is not None and user_row.wallet_balance_rial == 10_000 + amount

    _, kwargs = _post(app, body)
    response = await client.post("/internal/sms", **kwargs)
    assert (await response.json())["outcome"] == "duplicate-sms"
    async with factory() as session:
        assert len((await session.scalars(select(SmsMessage))).all()) == 1
