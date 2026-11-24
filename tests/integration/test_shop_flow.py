"""M3 end-to-end: browse catalog → add to cart → change qty → remove."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings
from app.db.models import CartItem, Category, Product, User
from tests.conftest import truncate_all
from tests.fakes import FakeSession, callback_update, make_message, message_update

USER_ID = 6001
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
            stock_qty=5,
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


async def test_shop_flow(env) -> None:
    await _feed(env, message_update(make_message(user_id=USER_ID, text="🛍 فروشگاه")))
    texts = env.fake.sent_texts(USER_ID)
    assert any("دستهبندیها" in text for text in texts)
    assert any(
        button["callback_data"] == f"cat:{env.category_id}"
        for call in env.fake.calls
        if call["method"] == "SendMessage" and call["data"].get("chat_id") == USER_ID
        for row in call["data"]["reply_markup"]["inline_keyboard"]
        for button in row
    )

    await _feed(env, callback_update(user_id=USER_ID, data=f"cat:{env.category_id}", message_id=2))
    await _feed(env, callback_update(user_id=USER_ID, data=f"p:{env.product_id}", message_id=3))
    assert any("چای سبز" in text for text in env.fake.sent_texts(USER_ID))

    await _feed(env, callback_update(user_id=USER_ID, data=f"a:{env.product_id}", message_id=4))
    from sqlalchemy import select

    async with env.factory() as session:
        items = list(await session.scalars(select(CartItem)))
        assert len(items) == 1 and items[0].qty == 1
        item_id = items[0].id

    await _feed(env, callback_update(user_id=USER_ID, data=f"q:{item_id}:1", message_id=5))
    async with env.factory() as session:
        item = await session.get(CartItem, item_id)
        assert item is not None and item.qty == 2

    cart_msg = make_message(user_id=USER_ID, text="🧺 سبد خرید", message_id=6)
    await _feed(env, message_update(cart_msg))
    assert any("جمع کل" in text for text in env.fake.sent_texts(USER_ID))

    await _feed(env, callback_update(user_id=USER_ID, data=f"d:{item_id}", message_id=7))
    async with env.factory() as session:
        assert list(await session.scalars(select(CartItem))) == []
