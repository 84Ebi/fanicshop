"""M6: admin browsable all-users list + direct message action."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings
from app.db.models import SupportMessage, SupportThread, User
from tests.conftest import truncate_all
from tests.fakes import FakeSession, callback_update, make_message, message_update

ADMIN_ID = 9012
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
        users = [
            User(
                telegram_id=7001, full_name="الف", status="verified", phone="9110000001"
            ),
            User(
                telegram_id=7002, full_name="ب", status="verified", phone="9110000002"
            ),
            User(
                telegram_id=7003, full_name="ج", status="pending", phone="9110000003"
            ),
            User(
                telegram_id=7004, full_name="د", status="blocked", phone="9110000004"
            ),
        ]
        session.add_all(users)
        await session.commit()
        ids = {u.telegram_id: u.id for u in users}
    fake = FakeSession()
    bot = Bot(token=BOT_TOKEN, session=fake)
    dp = await build_dispatcher(settings, factory, storage=MemoryStorage())
    yield SimpleNamespace(dp=dp, bot=bot, fake=fake, factory=factory, ids=ids)
    await bot.session.close()
    await truncate_all(engine)


def _edit_markup(env) -> str:
    call = env.fake.last_call("EditMessageText")
    assert call is not None
    return str(call["data"].get("reply_markup"))


async def test_users_menu_and_all_list(env) -> None:
    await env.dp.feed_update(
        env.bot, callback_update(user_id=ADMIN_ID, data="adm:users", message_id=1)
    )
    assert "adm:all:all:0" in _edit_markup(env)

    await env.dp.feed_update(
        env.bot, callback_update(user_id=ADMIN_ID, data="adm:all:all:0", message_id=2)
    )
    markup = _edit_markup(env)
    for user_id in env.ids.values():
        assert f"adm:u:view:{user_id}" in markup

    # Verified-only filter excludes pending/blocked users.
    await env.dp.feed_update(
        env.bot, callback_update(user_id=ADMIN_ID, data="adm:all:verified:0", message_id=3)
    )
    markup = _edit_markup(env)
    assert f"adm:u:view:{env.ids[7002]}" in markup
    assert f"adm:u:view:{env.ids[7003]}" not in markup
    assert f"adm:u:view:{env.ids[7004]}" not in markup


async def test_user_card_message_action(env) -> None:
    target = env.ids[7001]
    await env.dp.feed_update(
        env.bot, callback_update(user_id=ADMIN_ID, data="adm:users", message_id=10)
    )
    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data="adm:all:all:0", message_id=11),
    )
    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data=f"adm:u:view:{target}", message_id=12),
    )
    assert f"adm:u:msg:{target}" in _edit_markup(env)

    await env.dp.feed_update(
        env.bot,
        callback_update(user_id=ADMIN_ID, data=f"adm:u:msg:{target}", message_id=13),
    )
    await env.dp.feed_update(
        env.bot,
        message_update(
            make_message(user_id=ADMIN_ID, text="پاسخ مستقیم", message_id=14), 14
        ),
    )
    texts = env.fake.sent_texts(7001)
    assert any("پاسخ مستقیم" in text for text in texts)

    async with env.factory() as session:
        thread = await session.scalar(
            select(SupportThread).where(SupportThread.user_id == target)
        )
        assert thread is not None
        msgs = list(
            (
                await session.scalars(
                    select(SupportMessage)
                    .where(SupportMessage.thread_id == thread.id)
                    .order_by(SupportMessage.id)
                )
            ).all()
        )
        assert [m.direction for m in msgs] == ["admin"]
