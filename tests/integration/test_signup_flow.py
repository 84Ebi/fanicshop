"""M2 end-to-end: signup wizard + admin approval over a fake Telegram transport."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Contact
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings
from app.db.models import User, UserEvent
from app.services.users import get_by_telegram_id
from tests.fakes import FakeSession, callback_update, make_message, message_update

USER_ID = 5001
ADMIN_ID = 9001
GROUP_ID = -1001234567890
BOT_TOKEN = "123456:TEST"


@pytest.fixture
async def env(engine, migrated_database):
    settings = Settings(
        _env_file=None,
        bot_token=BOT_TOKEN,
        admin_ids=str(ADMIN_ID),
        admin_roles=f"{ADMIN_ID}:owner",
        admin_group_chat_id=GROUP_ID,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    fake = FakeSession()
    bot = Bot(token=BOT_TOKEN, session=fake)
    dp = await build_dispatcher(settings, factory, storage=MemoryStorage())
    yield SimpleNamespace(dp=dp, bot=bot, fake=fake, factory=factory, settings=settings)
    await bot.session.close()


async def _feed(env, update) -> None:
    await env.dp.feed_update(env.bot, update)


async def _signup(env, user_id: int, name: str, phone: str) -> User:
    await _feed(env, message_update(make_message(user_id=user_id, text="/start")))
    await _feed(env, callback_update(user_id=user_id, data="age:yes", message_id=2))
    await _feed(
        env, message_update(make_message(user_id=user_id, text=name, message_id=3))
    )
    contact = Contact(phone_number=phone, first_name=name, user_id=user_id)
    await _feed(
        env,
        message_update(
            make_message(user_id=user_id, message_id=4, contact=contact)
        ),
    )
    await _feed(env, callback_update(user_id=user_id, data="su:ok", message_id=5))
    async with env.factory() as session:
        user = await get_by_telegram_id(session, user_id)
        assert user is not None
        return user


async def test_signup_and_admin_approval(env) -> None:
    await _feed(env, message_update(make_message(user_id=USER_ID, text="/start")))
    assert any("۱۸ سال" in text for text in env.fake.sent_texts(USER_ID))

    await _feed(env, callback_update(user_id=USER_ID, data="age:yes", message_id=2))
    await _feed(
        env, message_update(make_message(user_id=USER_ID, text="علی رضایی", message_id=3))
    )
    assert any("شماره موبایل" in text for text in env.fake.sent_texts(USER_ID))

    contact = Contact(phone_number="09121234567", first_name="علی", user_id=USER_ID)
    await _feed(
        env,
        message_update(make_message(user_id=USER_ID, message_id=4, contact=contact)),
    )
    confirm_text = env.fake.sent_texts(USER_ID)[-1]
    assert "علی رضایی" in confirm_text
    assert "۰۹۱۲ ۱۲۳ ۴۵۶۷" in confirm_text

    await _feed(env, callback_update(user_id=USER_ID, data="su:ok", message_id=5))
    async with env.factory() as session:
        user = await get_by_telegram_id(session, USER_ID)
        assert user is not None and user.status == "pending"
        events = list(
            await session.scalars(
                select(UserEvent).where(UserEvent.user_id == user.id).order_by(UserEvent.id)
            )
        )
        assert [e.event for e in events] == ["signup", "age_confirm", "submitted"]

    admin_texts = env.fake.sent_texts(ADMIN_ID)
    assert any("ثبت‌نام جدید" in text for text in admin_texts)
    assert any("ثبت‌نام جدید" in text for text in env.fake.sent_texts(GROUP_ID))

    notification = next(
        call
        for call in env.fake.calls
        if call["method"] == "SendMessage"
        and call["data"].get("chat_id") == ADMIN_ID
        and "ثبت‌نام جدید" in (call["data"].get("text") or "")
    )
    keyboard = notification["data"]["reply_markup"]["inline_keyboard"]
    callbacks = [button["callback_data"] for row in keyboard for button in row]
    assert f"adm:u:ok:{user.id}" in callbacks

    # Admin panel → pending queue → approve
    await _feed(env, message_update(make_message(user_id=ADMIN_ID, text="/admin", message_id=10)))
    assert any("پنل مدیریت" in text for text in env.fake.sent_texts(ADMIN_ID))

    await _feed(
        env, callback_update(user_id=ADMIN_ID, data="adm:pending:0", message_id=11)
    )
    assert any("در انتظار تأیید" in text for text in env.fake.sent_texts(ADMIN_ID))

    await _feed(
        env,
        callback_update(user_id=ADMIN_ID, data=f"adm:u:ok:{user.id}", message_id=12),
    )
    async with env.factory() as session:
        approved = await session.get(User, user.id)
        assert approved is not None and approved.status == "verified"
        approve_events = await session.scalar(
            select(func.count())
            .select_from(UserEvent)
            .where(UserEvent.user_id == user.id, UserEvent.event == "approve")
        )
        assert approve_events == 1

    assert any("تأیید شد" in text for text in env.fake.sent_texts(USER_ID))

    # Double-tap approve must not write a second event.
    await _feed(
        env,
        callback_update(user_id=ADMIN_ID, data=f"adm:u:ok:{user.id}", message_id=13),
    )
    async with env.factory() as session:
        approve_events = await session.scalar(
            select(func.count())
            .select_from(UserEvent)
            .where(UserEvent.user_id == user.id, UserEvent.event == "approve")
        )
        assert approve_events == 1
    last = env.fake.last_call("AnswerCallbackQuery")
    assert last is not None
    assert last["data"]["text"] == "این کاربر قبلاً تأیید شده است."


async def test_pending_user_cannot_open_shop(env) -> None:
    await _signup(env, 5002, "رضا احمدی", "09121234568")
    await _feed(
        env,
        message_update(make_message(user_id=5002, text="🛍 فروشگاه", message_id=20)),
    )
    last = env.fake.sent_texts(5002)[-1]
    assert "در انتظار تأیید" in last
    assert "به‌زودی" not in last


async def test_non_admin_cannot_open_admin_panel(env) -> None:
    await _feed(
        env,
        message_update(make_message(user_id=7777, text="/admin", message_id=30)),
    )
    assert any("دسترسی" in text for text in env.fake.sent_texts(7777))
