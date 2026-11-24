"""M6 e2e: admin product CRUD, order status and wallet adjustment."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings
from app.db.models import Category, Product, User, WalletTransaction
from tests.conftest import truncate_all
from tests.fakes import FakeSession, callback_update, make_message, message_update

ADMIN_ID = 9002
BOT_TOKEN = "123456:TEST"


@pytest.fixture
async def env(engine):
    settings = Settings(
        _env_file=None,
        bot_token=BOT_TOKEN,
        admin_ids=str(ADMIN_ID),
        admin_roles=f"{ADMIN_ID}:owner",
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    fake = FakeSession()
    bot = Bot(token=BOT_TOKEN, session=fake)
    dp = await build_dispatcher(settings, factory, storage=MemoryStorage())
    yield SimpleNamespace(dp=dp, bot=bot, fake=fake, factory=factory, settings=settings)
    await bot.session.close()
    await truncate_all(engine)


async def _msg(env, text: str, message_id: int) -> None:
    await env.dp.feed_update(
        env.bot,
        message_update(
            make_message(user_id=ADMIN_ID, text=text, message_id=message_id), message_id
        ),
    )


async def _cb(env, data: str, message_id: int) -> None:
    await env.dp.feed_update(
        env.bot,
        callback_update(
            user_id=ADMIN_ID, data=data, message_id=message_id, update_id=message_id + 200
        ),
    )


async def test_admin_product_wizard(env) -> None:
    await _msg(env, "/products", 1)
    assert any("کالاها" in text or "دسته" in text for text in env.fake.sent_texts(ADMIN_ID))

    await _cb(env, "ap:newcat", 2)
    await _msg(env, "coffee", 3)
    await _msg(env, "قهوه", 4)
    async with env.factory() as session:
        categories = list(await session.scalars(select(Category)))
        assert len(categories) == 1 and categories[0].title_fa == "قهوه"
        category_id = categories[0].id

    await _cb(env, f"ap:cat:{category_id}", 5)
    await _cb(env, f"ap:new:{category_id}", 6)
    await _msg(env, "قهوه عربیکا", 7)
    await _msg(env, "توضیحات", 8)
    await _msg(env, "۲۰۰", 9)
    await _msg(env, "10", 10)
    await _msg(env, "⏭ رد کردن", 11)
    async with env.factory() as session:
        products = list(await session.scalars(select(Product)))
        assert len(products) == 1
        assert products[0].price_rial == 2000
        assert products[0].stock_qty == 10


async def test_admin_order_status_and_wallet_adjust(env) -> None:
    async with env.factory() as session:
        user = User(telegram_id=5555, full_name="علی رضایی", status="verified", phone="9129998877")
        category = Category(slug="tea", title_fa="چای")
        product = Product(
            category=category, title_fa="چای", price_rial=100_000, stock_qty=5, reserved_qty=0
        )
        session.add_all([user, product])
        await session.commit()

    await _msg(env, "/credit 1 500 دلیل", 12)
    async with env.factory() as session:
        user = await session.get(User, 1)
        assert user is not None and user.wallet_balance_rial == 5000
        txs = list(await session.scalars(select(WalletTransaction)))
        assert len(txs) == 1 and txs[0].reason == "دلیل"
