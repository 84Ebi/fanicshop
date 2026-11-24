"""Signup wizard: name → phone (contact or manual) → confirm → pending."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import signup_admin_keyboard, signup_confirm_keyboard
from app.bot.keyboards.reply import phone_keyboard, remove_keyboard
from app.bot.states import Signup
from app.config import Settings
from app.i18n import t
from app.services.notifications import notify_signup_admins
from app.services.users import (
    InvalidProfile,
    InvalidTransition,
    PhoneTaken,
    display_name,
    submit_signup,
)
from app.utils.digits import fa_digits
from app.utils.names import normalize_name
from app.utils.phone import display_phone, normalize_phone

router = Router(name="signup")


@router.message(Signup.full_name, F.text)
async def name_step(message: Message, state: FSMContext) -> None:
    name = normalize_name(message.text)
    if name is None:
        await message.answer(t("signup.name_invalid"))
        return
    await state.update_data(full_name=name)
    await state.set_state(Signup.phone)
    await message.answer(t("signup.phone_ask"), reply_markup=phone_keyboard())


async def _accept_phone(message: Message, state: FSMContext, phone: str) -> None:
    data = await state.get_data()
    await state.update_data(phone=phone)
    await state.set_state(Signup.confirm)
    await message.answer(t("signup.phone_saved"), reply_markup=remove_keyboard())
    await message.answer(
        t(
            "signup.confirm_title",
            name=data["full_name"],
            phone=fa_digits(display_phone(phone)),
        ),
        reply_markup=signup_confirm_keyboard(),
    )


@router.message(Signup.phone, F.contact)
async def phone_contact(message: Message, state: FSMContext) -> None:
    contact = message.contact
    if contact is None or contact.user_id != message.from_user.id:
        await message.answer(t("signup.phone_wrong_contact"))
        return
    phone = normalize_phone(contact.phone_number)
    if phone is None:
        await message.answer(t("signup.phone_invalid"))
        return
    await _accept_phone(message, state, phone)


@router.message(Signup.phone, F.text == t("signup.phone_manual"))
async def phone_manual(message: Message) -> None:
    await message.answer(t("signup.phone_ask"), reply_markup=remove_keyboard())


@router.message(Signup.phone, F.text)
async def phone_text(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text)
    if phone is None:
        await message.answer(t("signup.phone_invalid"))
        return
    await _accept_phone(message, state, phone)


@router.callback_query(Signup.confirm, F.data == "su:ok")
async def confirm_signup(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user,
    bot: Bot,
    settings: Settings,
) -> None:
    if user is None or callback.from_user is None:
        await callback.answer(t("error.stale_state"), show_alert=True)
        return
    data = await state.get_data()
    name = data.get("full_name", "")
    phone = data.get("phone", "")
    try:
        await submit_signup(session, user, full_name=name, phone=phone)
    except PhoneTaken:
        await callback.answer(t("signup.phone_taken"), show_alert=True)
        return
    except (InvalidProfile, InvalidTransition):
        await callback.answer(t("error.stale_state"), show_alert=True)
        await state.clear()
        return

    await session.commit()
    await state.clear()

    if callback.message is not None:
        await callback.message.edit_text(t("signup.submitted"))
    await notify_signup_admins(
        bot,
        settings,
        user,
        reply_markup=signup_admin_keyboard(user.id),
    )
    await callback.answer()


@router.callback_query(Signup.confirm, F.data == "su:edit")
async def edit_signup(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Signup.full_name)
    if callback.message is not None:
        await callback.message.edit_text(t("signup.edit_ask"))
        await callback.message.answer(
            t("signup.name_ask"), reply_markup=remove_keyboard()
        )
    await callback.answer()
