"""M6: admin interactive order list + refund to wallet."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings
from app.db.models import Order, User
from tests.conftest import truncate_all
from tests.fakes import FakeSession, callback_update, make_message, message_update

ADMIN_ID = 9013
CUSTOMER_ID = 7801
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
    async with factory() as session:
        customer = User(
            telegram_id=CUSTOMER_ID,
            full_name="مشتری",
            status="verified",
            phone="9125556677",
            wallet_balance_rial=0,
        )
        session.add(customer)
        await session.flush()
        order = Order(
            public_code="F-REFUND1",
            user_id=customer.id,
            status="paid",
            payment_state="paid",
            subtotal_rial=100_000,
            total_rial=100_000,
            wallet_paid_rial=0,
            card_paid_rial=100_000,
            address_snapshot={"contact_kind": "phone", "contact": "9125556677"},
        )
        session.add(order)
        await session.commit()
        order_id = order.id
    fake = FakeSession()
    bot = Bot(token=BOT_TOKEN, session=fake)
    dp = await build_dispatcher(settings, factory, storage=MemoryStorage())
    yield SimpleNamespace(dp=dp, bot=bot, fake=fake, factory=factory, order_id=order_id)
    await bot.session.close()
    await truncate_all(engine)


def _edit_markup(env) -> str:
    call = env.fake.last_call("EditMessageText")
    assert call is not None
    return str(call["data"].get("reply_markup"))


async def test_orders_list_shows_row_and_refund(env) -> None:
    await env.dp.feed_update(
        env.bot, callback_update(user_id=ADMIN_ID, data="ao:list:all:0", message_id=1)
    )
    markup = _edit_markup(env)
    assert f"ao:view:{env.order_id}" in markup

    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data=f"ao:view:{env.order_id}", message_id=2),
    )
    assert f"aos:refund:{env.order_id}" in _edit_markup(env)

    await env.dp.feed_update(
        env.bot,
        callback_update(
            user_id=ADMIN_ID, data=f"aos:refund:{env.order_id}", message_id=3
        ),
    )
    await env.dp.feed_update(
        env.bot,
        message_update(
            make_message(user_id=ADMIN_ID, text="خطای کلی", message_id=4), 4
        ),
    )
    async with env.factory() as session:
        customer = await session.get(User, (await session.get(Order, env.order_id)).user_id)
        assert customer.wallet_balance_rial == 100_000
    texts = env.fake.sent_texts(CUSTOMER_ID)
    assert any("F-REFUND1" in text for text in texts)
