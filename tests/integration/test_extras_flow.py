"""M8 e2e: broadcast, sales report and customer support."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings
from app.db.models import Broadcast, BroadcastTarget, Order, User
from app.i18n import t
from tests.conftest import truncate_all
from tests.fakes import FakeSession, make_message, message_update

ADMIN_ID = 9004
CLIENT_A = 7771
CLIENT_B = 7772
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
        session.add_all(
            [
                User(telegram_id=CLIENT_A, full_name="الف", status="verified", phone="9121112222"),
                User(telegram_id=CLIENT_B, full_name="ب", status="verified", phone="9123334444"),
            ]
        )
        await session.commit()
    fake = FakeSession()
    bot = Bot(token=BOT_TOKEN, session=fake)
    dp = await build_dispatcher(settings, factory, storage=MemoryStorage())
    yield SimpleNamespace(dp=dp, bot=bot, fake=fake, factory=factory)
    await bot.session.close()
    await truncate_all(engine)


async def _admin_msg(env, text: str, message_id: int) -> None:
    await env.dp.feed_update(
        env.bot,
        message_update(
            make_message(user_id=ADMIN_ID, text=text, message_id=message_id), message_id
        ),
    )


async def test_broadcast_sends_to_verified_users(env) -> None:
    await _admin_msg(env, "/broadcast", 1)
    assert any("همگانی" in text for text in env.fake.sent_texts(ADMIN_ID))

    await _admin_msg(env, "حراج ویژه", 2)

    async with env.factory() as session:
        broadcast = (await session.scalars(select(Broadcast))).one()
        assert broadcast.status == "done"
        assert broadcast.sent_count == 2
        targets = list(await session.scalars(select(BroadcastTarget)))
        assert len(targets) == 2 and all(t.status == "sent" for t in targets)

    assert env.fake.sent_texts(CLIENT_A) and "حراج" in env.fake.sent_texts(CLIENT_A)[0]
    assert env.fake.sent_texts(CLIENT_B) and "حراج" in env.fake.sent_texts(CLIENT_B)[0]


async def test_report_counts_orders(env) -> None:
    async with env.factory() as session:
        paid_user = (await session.scalars(
            select(User).where(User.telegram_id == CLIENT_A)
        )).one()
        session.add_all(
            [
                Order(
                    public_code="P1",
                    user_id=paid_user.id,
                    subtotal_rial=100_000,
                    total_rial=100_000,
                    payment_state="paid",
                    status="paid",
                    address_snapshot={"line": "خیابان"},
                ),
                Order(
                    public_code="P2",
                    user_id=paid_user.id,
                    subtotal_rial=5_000,
                    total_rial=5_000,
                    payment_state="unpaid",
                    status="awaiting_payment",
                    address_snapshot={"line": "خیابان"},
                ),
            ]
        )
        await session.commit()

    await _admin_msg(env, "/report", 20)
    report = "\n".join(env.fake.sent_texts(ADMIN_ID))
    assert "گزارش فروش" in report
    assert "سفارشها: 2" in report
    assert "پرداختشده: 1" in report
    assert "۱۰٬۰۰۰" in report


async def test_support_message_notifies_admins(env) -> None:
    await env.dp.feed_update(
        env.bot,
        message_update(
            make_message(user_id=CLIENT_A, text=t("menu.support"), message_id=10), 10
        ),
    )
    await env.dp.feed_update(
        env.bot,
        message_update(
            make_message(user_id=CLIENT_A, text="مشکل در سفارش", message_id=11), 11
        ),
    )
    admin_texts = "\n".join(env.fake.sent_texts(ADMIN_ID))
    assert "مشکل در سفارش" in admin_texts
    assert any("پشتیبانی" in text for text in env.fake.sent_texts(CLIENT_A))
