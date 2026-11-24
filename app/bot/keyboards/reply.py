"""Reply keyboards (persistent bottom keyboards)."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.i18n import t


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("signup.phone_button"), request_contact=True)],
            [KeyboardButton(text=t("signup.phone_manual"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("menu.shop")), KeyboardButton(text=t("menu.cart"))],
            [KeyboardButton(text=t("menu.orders")), KeyboardButton(text=t("menu.wallet"))],
            [KeyboardButton(text=t("menu.profile")), KeyboardButton(text=t("menu.support"))],
        ],
        resize_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
