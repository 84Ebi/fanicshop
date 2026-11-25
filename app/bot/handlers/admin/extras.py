"""Admin broadcast & reports; customer support."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.guards import allow_message
from app.bot.keyboards.inline import (
    admin_support_menu_keyboard,
    paged_list_keyboard,
    support_thread_keyboard,
)
from app.bot.states import AdminBroadcast, SupportAdminReply, SupportFlow
from app.config import Settings
from app.db.models import Broadcast, BroadcastTarget, Order, SupportMessage, User
from app.i18n import money_rial, t
from app.services.notifications import notify_admins
from app.services.support import (
    append_support_message,
    count_broadcasts,
    count_threads,
    get_or_create_thread,
    get_thread,
    list_broadcasts,
    list_threads,
)
from app.utils.time import format_dt

admin_router = Router(name="admin_extras")
support_router = Router(name="support")


def _cb(callback: CallbackQuery) -> str:
    return callback.data or ""


async def _thread_messages(session: AsyncSession, thread_id: int) -> list[SupportMessage]:
    return list(
        (
            await session.scalars(
                select(SupportMessage)
                .where(SupportMessage.thread_id == thread_id)
                .order_by(SupportMessage.id)
            )
        ).all()
    )


async def _latest_thread_previews(
    session: AsyncSession, thread_ids: list[int]
) -> dict[int, str]:
    if not thread_ids:
        return {}
    rows = (
        await session.execute(
            select(SupportMessage.thread_id, SupportMessage.text).order_by(
                SupportMessage.id.desc()
            )
        )
    ).all()
    seen: set[int] = set()
    latest: dict[int, str] = {}
    for tid, text in rows:
        if tid in thread_ids and tid not in seen:
            latest[tid] = (text or "").replace("\n", " ")[:60]
            seen.add(tid)
    return latest


@admin_router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminBroadcast.text)
    await message.answer(t("admin.broadcast_ask"))


@admin_router.callback_query(F.data == "adm:goto:broadcast")
async def goto_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcast.text)
    if isinstance(callback.message, Message):
        await callback.message.answer(t("admin.broadcast_ask"))
    await callback.answer()


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


async def _report_text(session: AsyncSession) -> str:
    total = await session.scalar(select(func.count()).select_from(Order)) or 0
    paid = await session.scalar(
        select(func.count()).select_from(Order).where(Order.payment_state == "paid")
    ) or 0
    revenue = await session.scalar(
        select(func.coalesce(func.sum(Order.total_rial), 0)).where(
            Order.payment_state == "paid"
        )
    ) or 0
    return "\n".join(
        [
            t("admin.report_title"),
            t("admin.report_orders", count=total),
            t("admin.report_paid", count=paid),
            t("admin.report_revenue", amount=money_rial(int(revenue))),
        ]
    )


@admin_router.message(Command("report"))
async def report(message: Message, session: AsyncSession) -> None:
    await message.answer(await _report_text(session))


@admin_router.callback_query(F.data == "adm:goto:report")
async def goto_report(callback: CallbackQuery, session: AsyncSession) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(await _report_text(session))
    await callback.answer()


@admin_router.callback_query(F.data == "adm:goto:support")
async def goto_support(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("support.admin_menu"), reply_markup=admin_support_menu_keyboard()
        )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("sup:threads:"))
async def support_threads_list(callback: CallbackQuery, session: AsyncSession) -> None:
    page = int(_cb(callback).split(":")[2])
    threads = await list_threads(session, limit=8, offset=page * 8)
    total = await count_threads(session)
    has_next = (page + 1) * 8 < total
    latest = await _latest_thread_previews(session, [thread.id for thread in threads])
    items = [
        (f"#{thread.id} — {latest.get(thread.id, '-')}", f"sup:t:{thread.id}")
        for thread in threads
    ]
    text = t("support.threads_title", count=total)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text or t("support.empty"),
            reply_markup=paged_list_keyboard(
                items,
                page=page,
                has_next=has_next,
                prefix="sup:threads:",
                back_cb="adm:goto:support",
            ),
        )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("sup:bcast:"))
async def support_broadcast_log(callback: CallbackQuery, session: AsyncSession) -> None:
    page = int(_cb(callback).split(":")[2])
    broadcasts = await list_broadcasts(session, limit=8, offset=page * 8)
    total = await count_broadcasts(session)
    has_next = (page + 1) * 8 < total
    items = [
        (
            t(
                "support.broadcast_line",
                id=b.id,
                status=t(f"admin.broadcast_status.{b.status}"),
                sent=b.sent_count,
                failed=b.failed_count,
                date=format_dt(b.created_at),
            ),
            "sup:bcast:nop",
        )
        for b in broadcasts
    ]
    text = t("support.broadcast_title", count=total)
    if not items:
        text = t("support.broadcast_empty")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text,
            reply_markup=paged_list_keyboard(
                items, page=page, has_next=has_next, prefix="sup:bcast:", back_cb="adm:goto:support"
            ),
        )
    await callback.answer()


@admin_router.callback_query(F.data == "sup:bcast:nop")
async def support_broadcast_nop(callback: CallbackQuery) -> None:
    await callback.answer()


@admin_router.callback_query(F.data.startswith("sup:t:"))
async def support_thread_view(callback: CallbackQuery, session: AsyncSession) -> None:
    thread_id = int(_cb(callback).split(":")[2])
    thread = await get_thread(session, thread_id)
    if thread is None:
        await callback.answer(t("support.gone"), show_alert=True)
        return
    user = await session.get(User, thread.user_id)
    name = user.full_name if user else f"#{thread.user_id}"
    messages = await _thread_messages(session, thread.id)
    body = "\n".join(
        t(
            "support.thread_line",
            who=(
                t("support.customer") if m.direction == "user" else t("support.admin")
            ),
            text=(m.text or "")[:300],
            time=format_dt(m.created_at),
        )
        for m in messages
    )
    text = (
        t("support.thread_title", id=thread.id, name=name)
        + "\n\n"
        + (body or t("support.empty"))
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text, reply_markup=support_thread_keyboard(thread)
        )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("sup:r:"))
async def support_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    thread_id = int(_cb(callback).split(":")[2])
    await state.set_state(SupportAdminReply.text)
    await state.update_data(thread_id=thread_id)
    if isinstance(callback.message, Message):
        await callback.message.answer(t("support.reply_ask"))
    await callback.answer()


@admin_router.message(SupportAdminReply.text, F.text)
async def support_reply_send(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    data = await state.get_data()
    await state.clear()
    thread = await get_thread(session, int(data.get("thread_id", 0)))
    if thread is None:
        await message.answer(t("support.gone"))
        return
    user = await session.get(User, thread.user_id)
    text = (message.text or "")[:2000]
    if user is not None:
        try:
            await bot.send_message(user.telegram_id, text)
        except Exception:  # noqa: BLE001 - delivery is best-effort
            pass
    await append_support_message(
        session, thread_id=thread.id, direction="admin", text=text
    )
    await session.commit()
    await message.answer(t("support.sent"))


@admin_router.callback_query(F.data.startswith("sup:c:"))
async def support_thread_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    thread_id = int(_cb(callback).split(":")[2])
    thread = await get_thread(session, thread_id)
    if thread is None:
        await callback.answer(t("support.gone"), show_alert=True)
        return
    thread.is_open = not thread.is_open
    await session.commit()
    user = await session.get(User, thread.user_id)
    name = user.full_name if user else f"#{thread.user_id}"
    messages = await _thread_messages(session, thread.id)
    body = "\n".join(
        t(
            "support.thread_line",
            who=(
                t("support.customer") if m.direction == "user" else t("support.admin")
            ),
            text=(m.text or "")[:300],
            time=format_dt(m.created_at),
        )
        for m in messages
    )
    text = (
        t("support.thread_title", id=thread.id, name=name)
        + "\n\n"
        + (body or t("support.empty"))
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=support_thread_keyboard(thread))
    await callback.answer()


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
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    user: User | None,
) -> None:
    await state.clear()
    if user is not None:
        thread = await get_or_create_thread(session, user.id)
        thread.is_open = True
        await append_support_message(
            session,
            thread_id=thread.id,
            direction="user",
            text=(message.text or "")[:2000],
        )
        await session.commit()
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
