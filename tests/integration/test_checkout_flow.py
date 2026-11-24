"""M4 end-to-end: add to cart → address wizard → note → place order."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings
from app.db.models import Category, Order, Product, User
from tests.conftest import truncate_all
from tests.fakes import FakeSession, callback_update, make_message, message_update

USER_ID = 8002
BOT_TOKEN = "123456:TEST"


@pytest.fixture
async def env(engine):
    settings = Settings(
        _env_file=None, bot_token=BOT_TOKEN, admin_ids="9001", delivery_fee_rial=5_000
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        category = Category(slug="spice", title_fa="ادویه")
        product = Product(
            category=category,
            title_fa="زعفران",
            price_rial=500_000,
            stock_qty=4,
            reserved_qty=0,
        )
        user = User(
            telegram_id=USER_ID,
            full_name="علی رضایی",
            status="verified",
            phone="9121234567",
        )
        session.add_all([product, user])
        await session.commit()
        category_id, product_id = category.id, product.id
    fake = FakeSession()
    bot = Bot(token=BOT_TOKEN, session=fake)
    dp = await build_dispatcher(settings, factory, storage=MemoryStorage())
    yield SimpleNamespace(
        dp=dp, bot=bot, fake=fake, factory=factory, category_id=category_id, product_id=product_id
    )
    await bot.session.close()
    await truncate_all(engine)


async def _feed(env, update) -> None:
    await env.dp.feed_update(env.bot, update)


async def _msg(env, text: str, message_id: int) -> None:
    update = message_update(
        make_message(user_id=USER_ID, text=text, message_id=message_id), message_id
    )
    await _feed(env, update)


async def _cb(env, data: str, message_id: int) -> None:
    update = callback_update(
        user_id=USER_ID, data=data, message_id=message_id, update_id=message_id + 100
    )
    await _feed(env, update)


async def test_full_checkout(env) -> None:
    await _msg(env, "🛍 فروشگاه", 1)
    await _cb(env, f"cat:{env.category_id}", 2)
    await _cb(env, f"p:{env.product_id}", 3)
    await _cb(env, f"a:{env.product_id}", 4)
    await _cb(env, "checkout", 5)

    await _msg(env, "علی رضایی", 6)
    await _msg(env, "09121234567", 7)
    await _msg(env, "تهران", 8)
    await _msg(env, "تهران", 9)
    await _msg(env, "خیابان آزادی، پلاک ۱۲", 10)
    await _msg(env, "1234567890", 11)
    await _cb(env, "co:ok", 12)

    async with env.factory() as session:
        orders = list(await session.scalars(select(Order)))
        assert len(orders) == 1
        order = orders[0]
        assert order.status == "awaiting_payment"
        assert order.total_rial == 505_000
        assert order.delivery_note is None
        product = await session.get(Product, env.product_id)
        assert product is not None and product.reserved_qty == 1

    texts = env.fake.sent_texts(USER_ID)
    assert any("F-" in text for text in texts)


async def test_orders_list_and_cancel(env) -> None:
    await _msg(env, "🛍 فروشگاه", 20)
    await _cb(env, f"cat:{env.category_id}", 21)
    await _cb(env, f"p:{env.product_id}", 22)
    await _cb(env, f"a:{env.product_id}", 23)
    await _cb(env, "checkout", 24)
    for i, value in enumerate(
        ["علی رضایی", "09121234567", "تهران", "تهران", "خیابان آزادی، پلاک ۱۲", "1234567890"],
        start=25,
    ):
        await _msg(env, value, i)
    await _cb(env, "co:ok", 31)

    await _msg(env, "📦 سفارش‌های من", 32)
    assert any("سفارش" in text and "من" in text for text in env.fake.sent_texts(USER_ID))

    async with env.factory() as session:
        order = (await session.scalars(select(Order))).first()
        assert order is not None
        order_id = order.id

    await _cb(env, f"oc:{order_id}", 33)
    async with env.factory() as session:
        order = await session.get(Order, order_id)
        assert order is not None and order.status == "cancelled"
        product = await session.get(Product, env.product_id)
        assert product is not None and product.reserved_qty == 0
