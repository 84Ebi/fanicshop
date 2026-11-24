"""Admin broadcast & reports; customer support."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.guards import allow_message
from app.bot.states import AdminBroadcast, SupportFlow
from app.config import Settings
from app.db.models import Broadcast, BroadcastTarget, Order, User
from app.i18n import money_rial, t
from app.services.notifications import notify_admins

admin_router = Router(name="admin_extras")
support_router = Router(name="support")


@admin_router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminBroadcast.text)
    await message.answer(t("admin.broadcast_ask"))


@admin_router.message(AdminBroadcast.text, F.text)
async def broadcast_send(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    text = (message.text or "").strip()
    await state.clear()
    users = list(
        await session.scalars(select(User).where(User.status == "verified"))
    )
    if not users:
        await message.answer(t("admin.broadcast_empty"))
        return
    broadcast = Broadcast(
        text=text,
        created_by=message.from_user.id if message.from_user else None,
        status="running",
        total_targets=len(users),
    )
    session.add(broadcast)
    await session.flush()
    sent = failed = 0
    for user in users:
        target = BroadcastTarget(broadcast_id=broadcast.id, user_id=user.id, status="queued")
        session.add(target)
        await session.flush()
        try:
            await bot.send_message(user.telegram_id, text)
            target.status = "sent"
            sent += 1
        except Exception:  # noqa: BLE001 - a blocked user must not stop the broadcast
            target.status = "blocked"
            failed += 1
    broadcast.sent_count = sent
    broadcast.failed_count = failed
    broadcast.status = "done"
    await session.commit()
    await message.answer(t("admin.broadcast_done", count=sent))


@admin_router.message(Command("report"))
async def report(message: Message, session: AsyncSession) -> None:
    total = await session.scalar(select(func.count()).select_from(Order)) or 0
    paid = await session.scalar(
        select(func.count()).select_from(Order).where(Order.payment_state == "paid")
    ) or 0
    revenue = await session.scalar(
        select(func.coalesce(func.sum(Order.total_rial), 0)).where(
            Order.payment_state == "paid"
        )
    ) or 0
    await message.answer(
        "\n".join(
            [
                t("admin.report_title"),
                t("admin.report_orders", count=total),
                t("admin.report_paid", count=paid),
                t("admin.report_revenue", amount=money_rial(int(revenue))),
            ]
        )
    )


@admin_router.message(Command("reply"))
async def support_reply(message: Message, session: AsyncSession, bot: Bot) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(t("support.reply_usage"))
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer(t("support.reply_usage"))
        return
    try:
        await bot.send_message(user_id, parts[2])
        await message.answer(t("support.sent"))
    except Exception:  # noqa: BLE001 - delivery is best-effort
        await message.answer(t("admin.invalid_user"))


@support_router.message(F.text == t("menu.support"))
async def support_start(message: Message, state: FSMContext, user: User | None) -> None:
    if not await allow_message(message, user):
        return
    await state.set_state(SupportFlow.message)
    await message.answer(t("support.ask"))


@support_router.message(SupportFlow.message, F.text)
async def support_message(
    message: Message, state: FSMContext, bot: Bot, settings: Settings
) -> None:
    await state.clear()
    await notify_admins(
        bot,
        settings,
        t(
            "support.new",
            name=(message.from_user.first_name if message.from_user else "-"),
            id=message.from_user.id if message.from_user else "-",
            text=(message.text or "")[:500],
        ),
    )
    await message.answer(t("support.sent"))
