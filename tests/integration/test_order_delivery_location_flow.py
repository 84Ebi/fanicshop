"""M6: admin sends a delivery location to verify an order (TASK-060)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Location, Message, Update, User
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings
from app.db.models import Category, Order, Product
from app.db.models import User as DbUser
from app.services.cart import add_item
from app.services.orders import create_order
from tests.conftest import truncate_all
from tests.fakes import FakeSession, callback_update

ADMIN_ID = 9005
CUSTOMER_ID = 6601
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
        customer = DbUser(
            telegram_id=CUSTOMER_ID, full_name="مشتری", status="verified", phone="9125556677"
        )
        category = Category(slug="tea", title_fa="چای", sort_order=1)
        product = Product(
            category=category, title_fa="چای", price_rial=100_000, stock_qty=5, reserved_qty=0
        )
        session.add_all([customer, product])
        await session.flush()
        await add_item(session, customer.id, product, 1)
        order = await create_order(
            session, user_id=customer.id, contact_kind="telegram_id", contact=str(CUSTOMER_ID)
        )
        await session.commit()
        order_id = order.id
    fake = FakeSession()
    bot = Bot(token=BOT_TOKEN, session=fake)
    dp = await build_dispatcher(settings, factory, storage=MemoryStorage())
    yield SimpleNamespace(dp=dp, bot=bot, fake=fake, factory=factory, order_id=order_id)
    await bot.session.close()
    await truncate_all(engine)


def _admin_location_update(message_id: int, update_id: int) -> Update:
    loc = Location(latitude=35.6892, longitude=51.3890)
    msg = Message(
        message_id=message_id,
        date=datetime.now(UTC),
        chat=Chat(id=ADMIN_ID, type="private"),
        from_user=User(id=ADMIN_ID, is_bot=False, first_name="ادمین"),
        location=loc,
    )
    return Update(update_id=update_id, message=msg)


async def test_admin_sends_location_and_verifies_order(env) -> None:
    await env.dp.feed_update(
        env.bot, callback_update(user_id=ADMIN_ID, data=f"ao:view:{env.order_id}", message_id=40)
    )
    # The order detail edit carries the location button.
    edit_call = env.fake.last_call("EditMessageText")
    assert edit_call is not None
    assert f"ao:loc:{env.order_id}" in str(edit_call["data"].get("reply_markup"))

    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data=f"ao:loc:{env.order_id}", message_id=41),
    )
    admin_texts = env.fake.sent_texts(ADMIN_ID)
    assert any("مکان" in text for text in admin_texts)

    await env.dp.feed_update(env.bot, _admin_location_update(42, 500))

    async with env.factory() as session:
        order = await session.get(Order, env.order_id)
        assert order is not None
        assert order.status == "preparing"
        assert order.delivery_location == {"latitude": 35.6892, "longitude": 51.3890}

    # The customer was notified and received the location point.
    customer_texts = env.fake.sent_texts(CUSTOMER_ID)
    assert any("تأیید" in text for text in customer_texts)
    loc_call = env.fake.last_call("SendLocation")
    assert loc_call is not None
    assert int(loc_call["data"]["chat_id"]) == CUSTOMER_ID
    assert loc_call["data"]["latitude"] == 35.6892
