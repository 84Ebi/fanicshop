"""Checkout wizard, order list/detail and cancellation (M4)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.guards import allow_callback, allow_message
from app.bot.keyboards.inline import (
    checkout_confirm_keyboard,
    order_keyboard,
    orders_keyboard,
)
from app.bot.keyboards.reply import checkout_contact_keyboard, main_menu_keyboard, remove_keyboard
from app.bot.states import Checkout
from app.config import Settings
from app.db.models import Order, OrderItem, User
from app.i18n import fa_digits, money_rial, t
from app.services.cart import get_or_create_cart, list_items
from app.services.orders import (
    EmptyCart,
    NoAddress,
    StockChanged,
    cancel_order,
    create_order,
    get_order,
    list_orders,
)
from app.utils.phone import display_phone, normalize_phone

router = Router(name="orders")


def _data(callback: CallbackQuery) -> str:
    return callback.data or ""


async def _edit(callback: CallbackQuery, text: str, markup=None) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


# ── order rendering ────────────────────────────────────────────────────────
async def _order_details(session: AsyncSession, order: Order) -> str:
    rows = (
        await session.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
        )
    ).all()
    lines = [
        t(
            "orders.line",
            index=str(index),
            title=item.title_snapshot,
            qty=str(item.qty),
            line_total=money_rial(item.line_total_rial),
        )
        for index, item in enumerate(rows, 1)
    ]
    body = "\n".join(lines) if lines else t("orders.no_items")
    snap = order.address_snapshot or {}
    if snap.get("contact_kind") == "phone":
        contact = t("orders.contact_phone", phone=fa_digits(display_phone(snap.get("contact", ""))))
    elif snap.get("contact_kind") == "telegram_id":
        contact = t("orders.contact_telegram_id", id=snap.get("contact", ""))
    else:
        contact = t("orders.contact_none")
    loc = order.delivery_location or {}
    location = (
        t("orders.delivery_location", label=loc.get("label") or "")
        if loc.get("latitude") is not None and loc.get("longitude") is not None
        else t("orders.delivery_location_pending")
    )
    return t(
        "orders.detail",
        code=order.public_code,
        status=t(f"orders.status.{order.status}"),
        items=body,
        subtotal=money_rial(order.subtotal_rial),
        delivery=money_rial(order.delivery_fee_rial),
        total=money_rial(order.total_rial),
        address=contact,
        location=location,
    )


# ── entry: cart → checkout, menu → orders ──────────────────────────────────
@router.callback_query(F.data == "checkout")
async def checkout_entry(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User | None,
    state: FSMContext,
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    cart = await get_or_create_cart(session, user.id)
    items = await list_items(session, cart.id)
    if not items:
        await _edit(callback, t("checkout.empty_cart"))
        return
    await state.set_state(Checkout.contact)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            t("checkout.contact_ask"), reply_markup=checkout_contact_keyboard()
        )
    await callback.answer()


@router.message(F.text == t("menu.orders"))
async def my_orders(message: Message, session: AsyncSession, user: User | None) -> None:
    if not await allow_message(message, user) or user is None:
        return
    orders = await list_orders(session, user.id)
    if not orders:
        await message.answer(t("orders.empty"))
        return
    await message.answer(t("orders.list_title"), reply_markup=orders_keyboard(orders))


# ── delivery contact (telegram id or phone only) ────────────────────────────
@router.message(Checkout.contact, F.contact)
async def contact_shared(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User | None,
) -> None:
    if not await allow_message(message, user) or user is None:
        return
    phone = normalize_phone(message.contact.phone_number) if message.contact else None
    if phone is None:
        await message.answer(t("checkout.invalid_phone"))
        return
    await state.update_data(contact_kind="phone", contact=phone)
    await message.answer(t("checkout.contact_saved"), reply_markup=remove_keyboard())
    await _show_confirm_message(message, session, user, state)


@router.message(Checkout.contact, F.text == t("checkout.use_telegram_id"))
async def contact_use_telegram_id(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User | None,
) -> None:
    if not await allow_message(message, user) or user is None:
        return
    if message.from_user is None:
        return
    await state.update_data(contact_kind="telegram_id", contact=str(message.from_user.id))
    await message.answer(t("checkout.contact_saved"), reply_markup=remove_keyboard())
    await _show_confirm_message(message, session, user, state)


# ── confirmation ───────────────────────────────────────────────────────────
def _contact_summary(data: dict) -> str:
    kind = data.get("contact_kind")
    value = data.get("contact") or ""
    if kind == "phone":
        return t("orders.contact_phone", phone=fa_digits(display_phone(value)))
    return t("orders.contact_telegram_id", id=value)


async def _show_confirm(
    callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext
) -> None:
    data = await state.get_data()
    await state.set_state(Checkout.confirm)
    text = await _checkout_summary(session, user.id, _contact_summary(data))
    await _edit(callback, text, checkout_confirm_keyboard())


async def _show_confirm_message(
    message: Message, session: AsyncSession, user: User, state: FSMContext
) -> None:
    data = await state.get_data()
    await state.set_state(Checkout.confirm)
    text = await _checkout_summary(session, user.id, _contact_summary(data))
    await message.answer(text, reply_markup=checkout_confirm_keyboard())


async def _checkout_summary(session: AsyncSession, user_id: int, contact: str) -> str:
    from app.bot.handlers.user.shop import cart_text

    cart = await get_or_create_cart(session, user_id)
    items = await list_items(session, cart.id)
    return t("checkout.summary", cart=await cart_text(session, items), contact=contact)


@router.callback_query(Checkout.confirm, F.data == "co:ok")
async def confirm_place(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User | None,
    state: FSMContext,
    settings: Settings,
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    data = await state.get_data()
    try:
        order = await create_order(
            session,
            user_id=user.id,
            contact_kind=data.get("contact_kind") or "telegram_id",
            contact=data.get("contact") or str(user.telegram_id),
            delivery_fee_rial=settings.delivery_fee_rial,
            actor_telegram_id=user.telegram_id,
        )
        await session.commit()
    except (EmptyCart, StockChanged, NoAddress):
        await callback.answer(t("orders.place_failed"), show_alert=True)
        await session.rollback()
        await state.clear()
        await _edit(callback, t("cart.empty"))
        return
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(t("checkout.created", code=order.public_code))
        await callback.message.answer(
            await _order_details(session, order), reply_markup=order_keyboard(order)
        )
        await callback.message.answer(t("menu.title"), reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(Checkout.confirm, F.data == "co:cancel")
async def confirm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _edit(callback, t("checkout.cancelled"))
    if isinstance(callback.message, Message):
        await callback.message.answer(t("menu.title"), reply_markup=main_menu_keyboard())


# ── order detail / cancel / pay ────────────────────────────────────────────
@router.callback_query(F.data.startswith("o:"))
async def order_detail(
    callback: CallbackQuery, session: AsyncSession, user: User | None
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    order = await get_order(session, user.id, int(_data(callback).split(":")[1]))
    if order is None:
        await callback.answer(t("orders.gone"), show_alert=True)
        return
    await _edit(callback, await _order_details(session, order), order_keyboard(order))


@router.callback_query(F.data.startswith("oc:"))
async def order_cancel(
    callback: CallbackQuery, session: AsyncSession, user: User | None
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    order = await get_order(session, user.id, int(_data(callback).split(":")[1]))
    if order is None:
        await callback.answer(t("orders.gone"), show_alert=True)
        return
    if not await cancel_order(session, order, actor_telegram_id=user.telegram_id):
        await callback.answer(t("orders.not_cancellable"), show_alert=True)
        await session.rollback()
        return
    await session.commit()
    await _edit(callback, await _order_details(session, order), order_keyboard(order))


@router.callback_query(F.data.startswith("dc:"))
async def confirm_receipt(
    callback: CallbackQuery, session: AsyncSession, user: User | None
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    from app.services.orders import confirm_delivery

    order = await get_order(session, user.id, int(_data(callback).split(":")[1]))
    if order is None:
        await callback.answer(t("orders.gone"), show_alert=True)
        return
    if not await confirm_delivery(session, order, actor_telegram_id=user.telegram_id):
        await callback.answer(t("admin.invalid_state"), show_alert=True)
        return
    await session.commit()
    await _edit(callback, t("orders.confirmed"))
    await callback.answer(t("orders.confirmed"))


