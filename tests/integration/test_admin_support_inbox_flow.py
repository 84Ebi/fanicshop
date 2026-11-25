"""M6: admin support inbox (threads, reply, close/reopen)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings
from app.db.models import Broadcast, SupportMessage, SupportThread, User
from app.i18n import t
from tests.conftest import truncate_all
from tests.fakes import FakeSession, callback_update, make_message, message_update

ADMIN_ID = 9011
CUSTOMER_ID = 7701
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
        )
        session.add(customer)
        await session.commit()
        customer_id = customer.id
    fake = FakeSession()
    bot = Bot(token=BOT_TOKEN, session=fake)
    dp = await build_dispatcher(settings, factory, storage=MemoryStorage())
    yield SimpleNamespace(
        dp=dp, bot=bot, fake=fake, factory=factory, customer_id=customer_id
    )
    await bot.session.close()
    await truncate_all(engine)


async def _customer_msg(env, text: str, message_id: int) -> None:
    await env.dp.feed_update(
        env.bot,
        message_update(
            make_message(user_id=CUSTOMER_ID, text=text, message_id=message_id),
            message_id,
        ),
    )


async def _thread_id(env) -> int:
    async with env.factory() as session:
        thread = await session.scalar(
            select(SupportThread).where(SupportThread.user_id == env.customer_id)
        )
        assert thread is not None
        return thread.id


async def test_support_thread_reply_flow(env) -> None:
    await _customer_msg(env, t("menu.support"), 10)
    await _customer_msg(env, "مشکل در سفارش", 11)

    # Admin was notified and the message was persisted as a customer message.
    admin_texts = "\n".join(env.fake.sent_texts(ADMIN_ID))
    assert "مشکل در سفارش" in admin_texts
    thread_id = await _thread_id(env)
    async with env.factory() as session:
        thread = await session.get(SupportThread, thread_id)
        assert thread is not None and thread.is_open is True
        msgs = list(
            (
                await session.scalars(
                    select(SupportMessage)
                    .where(SupportMessage.thread_id == thread_id)
                    .order_by(SupportMessage.id)
                )
            ).all()
        )
        assert [m.direction for m in msgs] == ["user"]

    # Admin opens support menu -> inbox -> thread view.
    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data="adm:goto:support", message_id=20),
    )
    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data="sup:threads:0", message_id=21),
    )
    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data=f"sup:t:{thread_id}", message_id=22),
    )
    view = "\n".join(env.fake.sent_texts(ADMIN_ID))
    assert "مشکل در سفارش" in view

    # Admin replies -> customer receives it and a reply message is stored.
    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data=f"sup:r:{thread_id}", message_id=23),
    )
    await env.dp.feed_update(
        env.bot,
        message_update(
            make_message(user_id=ADMIN_ID, text="پاسخ پشتیبانی", message_id=24), 24
        ),
    )
    customer_texts = env.fake.sent_texts(CUSTOMER_ID)
    assert any("پاسخ پشتیبانی" in text for text in customer_texts)
    async with env.factory() as session:
        msgs = list(
            (
                await session.scalars(
                    select(SupportMessage)
                    .where(SupportMessage.thread_id == thread_id)
                    .order_by(SupportMessage.id)
                )
            ).all()
        )
        assert [m.direction for m in msgs] == ["user", "admin"]


async def test_support_thread_close_reopen(env) -> None:
    await _customer_msg(env, t("menu.support"), 30)
    await _customer_msg(env, "سلام", 31)
    thread_id = await _thread_id(env)

    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data=f"sup:c:{thread_id}", message_id=32),
    )
    async with env.factory() as session:
        assert (await session.get(SupportThread, thread_id)).is_open is False

    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data=f"sup:c:{thread_id}", message_id=33),
    )
    async with env.factory() as session:
        assert (await session.get(SupportThread, thread_id)).is_open is True


async def test_broadcast_log_lists(env) -> None:
    async with env.factory() as session:
        session.add(
            Broadcast(
                text="پیام همگانی تست",
                status="done",
                total_targets=2,
                sent_count=2,
                failed_count=0,
            )
        )
        await session.commit()

    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data="sup:bcast:0", message_id=40),
    )
    call = env.fake.last_call("EditMessageText")
    assert call is not None
    assert "همگانی" in call["data"].get("text", "")
    markup = str(call["data"].get("reply_markup"))
    assert "کامل شده" in markup
    assert "sup:bcast:nop" in markup
