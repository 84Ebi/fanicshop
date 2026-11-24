"""Checkout wizard, order list/detail and cancellation (M4)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.guards import allow_callback, allow_message
from app.bot.keyboards.inline import (
    address_keyboard,
    checkout_confirm_keyboard,
    order_keyboard,
    orders_keyboard,
)
from app.bot.keyboards.reply import main_menu_keyboard
from app.bot.states import Checkout, NewAddress
from app.config import Settings
from app.db.models import Address, Order, OrderItem, User
from app.i18n import money_rial, t
from app.services.cart import get_or_create_cart, list_items
from app.services.orders import (
    EmptyCart,
    NoAddress,
    StockChanged,
    cancel_order,
    create_address,
    create_order,
    get_address,
    get_order,
    list_addresses,
    list_orders,
)

router = Router(name="orders")


def _data(callback: CallbackQuery) -> str:
    return callback.data or ""


def _text(message: Message) -> str:
    return message.text or ""


def _note_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("common.skip"), callback_data="co:skip")]]
    )


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
    addr = " - ".join(
        str(snap.get(key, "")) for key in ("province", "city", "address_line") if snap.get(key)
    )
    return t(
        "orders.detail",
        code=order.public_code,
        status=t(f"orders.status.{order.status}"),
        items=body,
        subtotal=money_rial(order.subtotal_rial),
        delivery=money_rial(order.delivery_fee_rial),
        total=money_rial(order.total_rial),
        address=addr,
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
    addresses = await list_addresses(session, user.id)
    if not addresses:
        await state.set_state(NewAddress.receiver)
        if isinstance(callback.message, Message):
            await callback.message.answer(
                t("address.receiver_ask"), reply_markup=main_menu_keyboard()
            )
        await callback.answer()
        return
    await state.set_state(Checkout.address)
    await _edit(callback, t("checkout.address_title"), address_keyboard(addresses))


@router.message(F.text == t("menu.orders"))
async def my_orders(message: Message, session: AsyncSession, user: User | None) -> None:
    if not await allow_message(message, user) or user is None:
        return
    orders = await list_orders(session, user.id)
    if not orders:
        await message.answer(t("orders.empty"))
        return
    await message.answer(t("orders.list_title"), reply_markup=orders_keyboard(orders))


# ── address selection / new address ────────────────────────────────────────
@router.callback_query(Checkout.address, F.data.startswith("addr:"))
async def address_chosen(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User | None,
    state: FSMContext,
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    raw = _data(callback).split(":", 1)[1]
    if raw == "new":
        await state.set_state(NewAddress.receiver)
        if isinstance(callback.message, Message):
            await callback.message.answer(t("address.receiver_ask"))
        await callback.answer()
        return
    address = await get_address(session, user.id, int(raw))
    if address is None:
        await callback.answer(t("address.gone"), show_alert=True)
        return
    await state.update_data(address_id=address.id)
    await state.set_state(Checkout.note)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(t("checkout.note_ask"), reply_markup=_note_keyboard())
    await callback.answer()


@router.callback_query(Checkout.note, F.data == "co:skip")
async def note_skipped(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User | None,
    state: FSMContext,
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    await state.update_data(delivery_note=None)
    await _show_confirm(callback, session, user, state)


# ── new address wizard ─────────────────────────────────────────────────────
@router.message(NewAddress.receiver, F.text)
async def new_receiver(message: Message, state: FSMContext) -> None:
    await state.update_data(receiver=_text(message).strip())
    await state.set_state(NewAddress.phone)
    await message.answer(t("address.phone_ask"))


@router.message(NewAddress.phone, F.text)
async def new_phone(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=_text(message).strip())
    await state.set_state(NewAddress.province)
    await message.answer(t("address.province_ask"))


@router.message(NewAddress.province, F.text)
async def new_province(message: Message, state: FSMContext) -> None:
    await state.update_data(province=_text(message).strip())
    await state.set_state(NewAddress.city)
    await message.answer(t("address.city_ask"))


@router.message(NewAddress.city, F.text)
async def new_city(message: Message, state: FSMContext) -> None:
    await state.update_data(city=_text(message).strip())
    await state.set_state(NewAddress.line)
    await message.answer(t("address.line_ask"))


@router.message(NewAddress.line, F.text)
async def new_line(message: Message, state: FSMContext) -> None:
    await state.update_data(line=_text(message).strip())
    await state.set_state(NewAddress.postal)
    await message.answer(t("address.postal_ask"))


@router.message(NewAddress.postal, F.text)
async def new_postal(
    message: Message, session: AsyncSession, user: User | None, state: FSMContext
) -> None:
    if not await allow_message(message, user) or user is None:
        return
    data = await state.get_data()
    try:
        address = await create_address(
            session,
            user.id,
            receiver_name=data.get("receiver", ""),
            receiver_phone=data.get("phone", ""),
            province=data.get("province", ""),
            city=data.get("city", ""),
            address_line=data.get("line", ""),
            postal_code=_text(message).strip() or None,
        )
        await session.commit()
    except ValueError:
        await message.answer(t("address.invalid"))
        return
    await state.update_data(address_id=address.id, delivery_note=None)
    await state.set_state(Checkout.confirm)
    await _show_confirm_message(message, session, user, state)


# ── confirmation ───────────────────────────────────────────────────────────
async def _show_confirm(
    callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext
) -> None:
    data = await state.get_data()
    address = await get_address(session, user.id, int(data.get("address_id", 0)))
    if address is None:
        await _edit(callback, t("address.gone"))
        await state.clear()
        return
    await state.set_state(Checkout.confirm)
    text = await _checkout_summary(session, user.id, address)
    await _edit(callback, text, checkout_confirm_keyboard())


async def _show_confirm_message(
    message: Message, session: AsyncSession, user: User, state: FSMContext
) -> None:
    data = await state.get_data()
    address = await get_address(session, user.id, int(data.get("address_id", 0)))
    if address is None:
        await message.answer(t("address.gone"))
        await state.clear()
        return
    await state.set_state(Checkout.confirm)
    text = await _checkout_summary(session, user.id, address)
    await message.answer(text, reply_markup=checkout_confirm_keyboard())


async def _checkout_summary(session: AsyncSession, user_id: int, address: Address) -> str:
    from app.bot.handlers.user.shop import cart_text

    cart = await get_or_create_cart(session, user_id)
    items = await list_items(session, cart.id)
    return t(
        "checkout.summary",
        cart=await cart_text(session, items),
        address=f"{address.province} - {address.city} - {address.address_line}",
    )


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
    address = await get_address(session, user.id, int(data.get("address_id", 0)))
    if address is None:
        await _edit(callback, t("address.gone"))
        await state.clear()
        return
    try:
        order = await create_order(
            session,
            user_id=user.id,
            address=address,
            delivery_note=data.get("delivery_note"),
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
    await _edit(
        callback,
        await _order_details(session, order),
        order_keyboard(order),
    )


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


