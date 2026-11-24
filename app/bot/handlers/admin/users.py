"""Admin: verification queue, user cards, approve/reject/block/unblock, search."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import (
    admin_panel_keyboard,
    admin_user_keyboard,
    back_to_panel_keyboard,
    pending_list_keyboard,
    user_results_keyboard,
)
from app.bot.states import AdminUserFlow
from app.db.models import User
from app.i18n import t
from app.services.notifications import notify_user
from app.services.users import (
    InvalidTransition,
    approve_user,
    block_user,
    count_pending,
    list_pending,
    reject_user,
    search_users,
    unblock_user,
)
from app.utils.digits import fa_digits
from app.utils.phone import display_phone
from app.utils.time import format_dt

router = Router(name="admin_users")

PAGE_SIZE = 8
DEFAULT_REASON = "بدون توضیح"


def _status_label(user: User) -> str:
    return t(f"profile.status.{user.status}")


def _card(user: User) -> str:
    return t(
        "admin.user_card",
        name=user.full_name,
        telegram_id=user.telegram_id,
        phone=fa_digits(display_phone(user.phone)),
        status=_status_label(user),
        date=format_dt(user.created_at),
    )


def _msg(callback: CallbackQuery) -> Message | None:
    return callback.message if isinstance(callback.message, Message) else None


def _parts(callback: CallbackQuery) -> list[str]:
    return (callback.data or "").split(":")


async def _edit(bot: Bot, chat_id: int, message_id: int, text: str, reply_markup=None) -> None:
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest:
        pass


@router.message(Command("admin"))
async def admin_panel(message: Message, session: AsyncSession) -> None:
    count = await count_pending(session)
    await message.answer(t("admin.panel"), reply_markup=admin_panel_keyboard(count))


@router.callback_query(F.data == "adm:panel")
async def back_to_panel(callback: CallbackQuery, session: AsyncSession) -> None:
    count = await count_pending(session)
    msg = _msg(callback)
    if msg is not None:
        await msg.edit_text(t("admin.panel"), reply_markup=admin_panel_keyboard(count))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:pending:"))
async def pending_queue(callback: CallbackQuery, session: AsyncSession) -> None:
    page = int(_parts(callback)[2])
    offset = page * PAGE_SIZE
    users = await list_pending(session, limit=PAGE_SIZE, offset=offset)
    total = await count_pending(session)
    msg = _msg(callback)
    if not users:
        if msg is not None:
            await msg.edit_text(t("admin.pending_empty"), reply_markup=back_to_panel_keyboard())
        await callback.answer()
        return
    text = t("admin.pending_title") + f"\n\n{t('admin.pending', count=total)}"
    if msg is not None:
        await msg.edit_text(
            text,
            reply_markup=pending_list_keyboard(users, page, has_next=offset + len(users) < total),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:u:view:"))
async def user_card(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await session.get(User, int(_parts(callback)[3]))
    if user is None:
        await callback.answer(t("admin.not_found"), show_alert=True)
        return
    msg = _msg(callback)
    if msg is not None:
        await msg.edit_text(_card(user), reply_markup=admin_user_keyboard(user))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:u:ok:"))
async def approve(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    actor_id = callback.from_user.id
    user = await session.get(User, int(_parts(callback)[3]))
    if user is None:
        await callback.answer(t("admin.not_found"), show_alert=True)
        return
    try:
        changed = await approve_user(session, user, actor_telegram_id=actor_id)
    except InvalidTransition:
        await callback.answer(t("admin.invalid_state"), show_alert=True)
        return
    if not changed:
        await callback.answer(t("admin.already_verified"), show_alert=True)
        return
    await session.commit()
    await notify_user(bot, session, user, t("notify.approved"))
    await session.commit()
    msg = _msg(callback)
    if msg is not None:
        await _edit(bot, msg.chat.id, msg.message_id, t("admin.approved"))
    await callback.answer(t("admin.approved"))


async def _ask_reason(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    flow: State,
    prompt: str,
) -> None:
    msg = _msg(callback)
    await state.set_state(flow)
    await state.update_data(
        user_id=int(_parts(callback)[3]),
        card_chat_id=msg.chat.id if msg else None,
        card_message_id=msg.message_id if msg else None,
    )
    if msg is not None:
        await msg.edit_text(prompt)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:u:no:"))
async def reject_start(callback: CallbackQuery, state: FSMContext) -> None:
    await _ask_reason(
        callback,
        state,
        flow=AdminUserFlow.reject_reason,
        prompt=t("admin.reject_reason_ask"),
    )


@router.callback_query(F.data.startswith("adm:u:blk:"))
async def block_start(callback: CallbackQuery, state: FSMContext) -> None:
    await _ask_reason(
        callback,
        state,
        flow=AdminUserFlow.block_reason,
        prompt=t("admin.block_reason_ask"),
    )


async def _finish_reason(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    *,
    action: str,
    reason: str,
) -> None:
    if message.from_user is None:
        return
    actor_id = message.from_user.id
    data = await state.get_data()
    user = await session.get(User, data.get("user_id"))
    await state.clear()
    if user is None:
        await message.answer(t("admin.not_found"))
        return

    try:
        if action == "reject":
            changed = await reject_user(session, user, actor_telegram_id=actor_id, reason=reason)
        else:
            changed = await block_user(session, user, actor_telegram_id=actor_id, reason=reason)
    except InvalidTransition:
        await message.answer(t("admin.invalid_state"))
        return
    if not changed:
        await message.answer(t("admin.invalid_state"))
        return

    await session.commit()
    notice = (
        t("notify.rejected", reason=reason)
        if action == "reject"
        else t("notify.blocked", reason=reason)
    )
    await notify_user(bot, session, user, notice)
    await session.commit()

    result = t("admin.rejected") if action == "reject" else t("admin.blocked")
    if data.get("card_chat_id") and data.get("card_message_id"):
        await _edit(bot, data["card_chat_id"], data["card_message_id"], result)
    await message.answer(result)


@router.message(AdminUserFlow.reject_reason, Command("skip"))
async def reject_skip(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await _finish_reason(message, state, session, bot, action="reject", reason=DEFAULT_REASON)


@router.message(AdminUserFlow.reject_reason, F.text)
async def reject_reason(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    reason = (message.text or "").strip()[:300] or DEFAULT_REASON
    await _finish_reason(message, state, session, bot, action="reject", reason=reason)


@router.message(AdminUserFlow.block_reason, Command("skip"))
async def block_skip(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await _finish_reason(message, state, session, bot, action="block", reason=DEFAULT_REASON)


@router.message(AdminUserFlow.block_reason, F.text)
async def block_reason(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    reason = (message.text or "").strip()[:300] or DEFAULT_REASON
    await _finish_reason(message, state, session, bot, action="block", reason=reason)


@router.callback_query(F.data.startswith("adm:u:unb:"))
async def unblock(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    actor_id = callback.from_user.id
    user = await session.get(User, int(_parts(callback)[3]))
    if user is None:
        await callback.answer(t("admin.not_found"), show_alert=True)
        return
    changed = await unblock_user(session, user, actor_telegram_id=actor_id)
    if not changed:
        await callback.answer(t("admin.invalid_state"), show_alert=True)
        return
    await session.commit()
    await notify_user(bot, session, user, t("notify.unblocked"))
    await session.commit()
    msg = _msg(callback)
    if msg is not None:
        await _edit(
            bot,
            msg.chat.id,
            msg.message_id,
            _card(user),
            admin_user_keyboard(user),
        )
    await callback.answer(t("admin.unblocked"))


@router.callback_query(F.data == "adm:users")
async def users_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminUserFlow.search)
    msg = _msg(callback)
    if msg is not None:
        await msg.edit_text(t("admin.search_hint"))
    await callback.answer()


@router.message(AdminUserFlow.search, F.text)
async def users_search(message: Message, state: FSMContext, session: AsyncSession) -> None:
    users = await search_users(session, message.text or "")
    await state.clear()
    if not users:
        await message.answer(t("admin.not_found"), reply_markup=back_to_panel_keyboard())
        return
    rows = "\n".join(
        t(
            "admin.user_row",
            name=u.full_name,
            phone=fa_digits(display_phone(u.phone)),
            status=_status_label(u),
            user_id=u.id,
        )
        for u in users
    )
    await message.answer(t("admin.user_list", rows=rows), reply_markup=user_results_keyboard(users))
