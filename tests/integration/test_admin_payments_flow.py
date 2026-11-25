"""M6 e2e: admin proof review and auto-settlement (TASK-054)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.setup import build_dispatcher
from app.config import Settings
from app.db.models import Category, Order, PaymentProof, Product, User
from app.services.cart import add_item
from app.services.orders import create_order
from app.services.payments import attach_proof, create_intent
from tests.conftest import truncate_all
from tests.fakes import FakeSession, callback_update, make_message, message_update

ADMIN_ID = 9003
CUSTOMER_ID = 5556
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
            session, user_id=customer.id, contact_kind="phone", contact="9125556677"
        )
        intent = await create_intent(
            session, user_id=customer.id, amount_rial=order.total_rial,
            purpose="order", settings=settings, order_id=order.id,
        )
        await attach_proof(session, intent, file_id="f000", message_id=1)
        await session.commit()
        order_id = order.id
    fake = FakeSession()
    bot = Bot(token=BOT_TOKEN, session=fake)
    dp = await build_dispatcher(settings, factory, storage=MemoryStorage())
    yield SimpleNamespace(dp=dp, bot=bot, fake=fake, factory=factory, order_id=order_id)
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


async def test_admin_approves_receipt_and_settles(env) -> None:
    # Admin lists pending proofs.
    await _msg(env, "/proofs", 1)
    assert any("پرداخت" in text or "رسید" in text for text in env.fake.sent_texts(ADMIN_ID))

    async with env.factory() as session:
        proof = (await session.scalars(
            select(PaymentProof).where(PaymentProof.status == "pending")
        )).one()
        proof_id = proof.id

    # Approve → settles the order.
    await _cb(env, f"proof:ok:{proof_id}", 2)

    async with env.factory() as session:
        order = await session.get(Order, env.order_id)
        assert order is not None
        assert order.status == "paid"
        assert order.card_paid_rial == order.total_rial
        proof = await session.get(PaymentProof, proof_id)
        assert proof is not None and proof.status == "approved"

    # Customer is notified.
    assert any("تأیید" in text for text in env.fake.sent_texts(CUSTOMER_ID))
