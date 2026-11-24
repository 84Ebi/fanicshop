"""`/start`, age gate and entry routing."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import age_keyboard
from app.bot.keyboards.reply import main_menu_keyboard, remove_keyboard
from app.bot.states import Signup
from app.i18n import t
from app.logging import get_logger
from app.services.users import (
    confirm_age,
    display_name,
    get_by_telegram_id,
    get_or_create_user,
)
from app.utils.digits import fa_digits
from app.utils.phone import display_phone

router = Router(name="start")
log = get_logger("start")


async def ensure_user(session: AsyncSession, from_user: TgUser) -> object:
    user = await get_by_telegram_id(session, from_user.id)
    if user is None:
        user, _ = await get_or_create_user(
            session,
            telegram_id=from_user.id,
            username=from_user.username,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
        )
        await session.commit()
    return user


async def _begin_signup(message: Message, state: FSMContext, user) -> None:
    if user.age_confirmed_at is None:
        await message.answer(t("start.welcome", name=display_name(user)))
        await message.answer(t("start.age_question"), reply_markup=age_keyboard())
        return
    await state.set_state(Signup.full_name)
    await message.answer(t("signup.name_ask"), reply_markup=remove_keyboard())


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user,
    bot: Bot,
) -> None:
    await state.clear()
    if message.from_user is None:
        return
    if user is None:
        user, _ = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        await session.commit()

    if user.status == "blocked":
        await message.answer(
            t("start.blocked", reason=user.block_reason or t("common.unknown"))
        )
        return
    if user.status == "pending":
        await message.answer(t("start.pending"))
        return
    if user.status == "verified":
        await message.answer(t("menu.title"), reply_markup=main_menu_keyboard())
        return
    if user.status == "rejected":
        await message.answer(
            t("start.rejected", reason=user.rejection_reason or t("common.unknown"))
        )

    await _begin_signup(message, state, user)


@router.callback_query(F.data == "age:yes")
async def age_yes(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user,
    bot: Bot,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    if user is None:
        user = await ensure_user(session, callback.from_user)
    await confirm_age(session, user)
    await session.commit()

    if callback.message is not None:
        await callback.message.edit_text(t("signup.age_ok"))
        await callback.message.answer(
            t("signup.name_ask"), reply_markup=remove_keyboard()
        )
    await state.set_state(Signup.full_name)
    await callback.answer()


@router.callback_query(F.data == "age:no")
async def age_no(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.edit_text(t("start.age_denied"))
    await callback.answer()
