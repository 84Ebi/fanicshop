"""Main menu (M2: profile + placeholders; shop/cart/orders land in M3+)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from app.bot.keyboards.reply import main_menu_keyboard
from app.i18n import t
from app.services.users import can_access_shop
from app.utils.digits import fa_digits
from app.utils.phone import display_phone

router = Router(name="menu")


async def _guard(message: Message, user) -> bool:
    if can_access_shop(user):
        return True
    if user is not None and user.status == "pending":
        await message.answer(t("start.pending"))
    elif user is not None and user.status == "blocked":
        await message.answer(t("start.blocked", reason=user.block_reason or t("common.unknown")))
    else:
        await message.answer(t("common.start_hint"))
    return False


@router.message(F.text == t("menu.profile"))
async def profile(message: Message, user) -> None:
    if not await _guard(message, user):
        return
    await message.answer(
        t(
            "profile.title",
            name=user.full_name,
            phone=fa_digits(display_phone(user.phone)),
            status=t(f"profile.status.{user.status}"),
        )
    )


@router.message(F.text.in_({t("menu.shop"), t("menu.cart"), t("menu.orders"), t("menu.wallet"), t("menu.support")}))
async def not_available(message: Message, user) -> None:
    if not await _guard(message, user):
        return
    await message.answer(t("common.not_available"))


@router.message(StateFilter(None), F.text)
async def fallback(message: Message, user) -> None:
    if can_access_shop(user):
        await message.answer(t("menu.title"), reply_markup=main_menu_keyboard())
    elif user is not None and user.status == "pending":
        await message.answer(t("start.pending"))
    else:
        await message.answer(t("common.start_hint"))
