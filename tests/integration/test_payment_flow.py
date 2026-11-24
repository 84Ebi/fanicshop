"""M5 end-to-end: order → payment method → card intent instructions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings
from app.db.models import Category, PaymentIntent, Product, User
from app.services.cart import add_item
from app.services.orders import create_address, create_order
from tests.fakes import FakeSession, callback_update

USER_ID = 6003
BOT_TOKEN = "123456:TEST"


@pytest.fixture
async def env(engine):
    settings = Settings(_env_file=None, bot_token=BOT_TOKEN, admin_ids="9001")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        category = Category(slug="tea", title_fa="چای", sort_order=1)
        product = Product(
            category=category,
            title_fa="چای سبز",
            description_fa="دم کرده",
            price_rial=120_000,
            stock_qty=10,
            reserved_qty=0,
        )
        user = User(
            telegram_id=USER_ID, full_name="علی رضایی", status="verified", phone="9121234567"
        )
        session.add_all([product, user])
        await session.flush()
        await add_item(session, user.id, product, 2)
        address = await create_address(
            session, user.id, receiver_name="علی رضایی", receiver_phone="09121234567",
            province="تهران", city="تهران", address_line="خیابان آزادی، پلاک ۱۲",
        )
        order = await create_order(session, user_id=user.id, address=address)
        await session.commit()
        order_id, user_id_db = order.id, user.id
    fake = FakeSession()
    bot = Bot(token=BOT_TOKEN, session=fake)
    dp = await build_dispatcher(settings, factory, storage=MemoryStorage())
    yield SimpleNamespace(
        dp=dp, bot=bot, fake=fake, factory=factory, order_id=order_id, user_id_db=user_id_db
    )
    await bot.session.close()


async def test_payment_flow_creates_intent(env) -> None:
    # Open the payment-method menu for the order.
    await env.dp.feed_update(
        env.bot, callback_update(user_id=USER_ID, data=f"pay:{env.order_id}", message_id=20)
    )
    texts = env.fake.sent_texts(USER_ID)
    assert any("پرداخت" in text for text in texts)

    # Choose card-to-card → a unique-amount intent is created.
    await env.dp.feed_update(
        env.bot, callback_update(user_id=USER_ID, data=f"pm:card:{env.order_id}", message_id=21)
    )
    texts = env.fake.sent_texts(USER_ID)
    assert any("شماره کارت" in text and "ریال" in text for text in texts)

    async with env.factory() as session:
        intent = (await session.scalars(
            select(PaymentIntent).where(PaymentIntent.order_id == env.order_id)
        )).one()
        assert intent.purpose == "order"
        assert intent.status == "pending"
        # unique-amount: expected = order total + random suffix
        assert intent.expected_amount_rial > intent.base_amount_rial
        assert intent.base_amount_rial == 240_000
