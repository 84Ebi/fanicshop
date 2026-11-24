"""Customer catalog browsing and cart management."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.guards import allow_callback, allow_message
from app.bot.keyboards.inline import (
    cart_keyboard,
    categories_keyboard,
    product_keyboard,
    products_keyboard,
)
from app.db.models import CartItem, Product, User
from app.i18n import fa_digits, money_rial, t
from app.services.cart import (
    OutOfStock,
    TooMany,
    add_item,
    clear,
    get_or_create_cart,
    list_items,
    remove_item,
    set_qty,
    subtotal,
)
from app.services.catalog import (
    first_image,
    get_category,
    get_product,
    list_categories,
    list_products,
    product_card,
)

router = Router(name="shop")


def _data(callback: CallbackQuery) -> str:
    return callback.data or ""


async def _edit(
    callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None
) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)


async def show_categories(message: Message, session: AsyncSession, user: User | None) -> None:
    if not await allow_message(message, user):
        return
    categories = await list_categories(session)
    if not categories:
        await message.answer(t("catalog.empty"))
        return
    await message.answer(t("catalog.title"), reply_markup=categories_keyboard(categories))


@router.message(F.text == t("menu.shop"))
async def shop_button(message: Message, session: AsyncSession, user: User | None) -> None:
    await show_categories(message, session, user)


@router.callback_query(F.data == "cats")
async def categories_callback(
    callback: CallbackQuery, session: AsyncSession, user: User | None
) -> None:
    if not await allow_callback(callback, user):
        return
    categories = await list_categories(session)
    await _edit(callback, t("catalog.title"), categories_keyboard(categories))
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def category_callback(
    callback: CallbackQuery, session: AsyncSession, user: User | None
) -> None:
    if not await allow_callback(callback, user):
        return
    category_id = int(_data(callback).split(":")[1])
    category = await get_category(session, category_id)
    if category is None:
        await callback.answer(t("catalog.empty"), show_alert=True)
        return
    products = await list_products(session, category_id)
    await _edit(
        callback,
        t("catalog.products_title", title=category.title_fa),
        products_keyboard(products, category_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("p:"))
async def product_callback(
    callback: CallbackQuery, session: AsyncSession, user: User | None, bot: Bot
) -> None:
    if not await allow_callback(callback, user):
        return
    product = await get_product(session, int(_data(callback).split(":")[1]))
    if product is None:
        await callback.answer(t("catalog.empty"), show_alert=True)
        return
    text = product_card(product)
    markup = product_keyboard(product)
    file_id = await first_image(session, product.id)
    if isinstance(callback.message, Message):
        if file_id:
            try:
                await bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=file_id,
                    caption=text,
                    reply_markup=markup,
                )
            except TelegramBadRequest:
                await _edit(callback, text, markup)
        else:
            await _edit(callback, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("a:"))
async def add_callback(callback: CallbackQuery, session: AsyncSession, user: User | None) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    product = await get_product(session, int(_data(callback).split(":")[1]))
    if product is None:
        await callback.answer(t("catalog.empty"), show_alert=True)
        return
    try:
        await add_item(session, user.id, product)
    except TooMany:
        await callback.answer(t("cart.qty_limit", limit=20), show_alert=True)
        return
    except OutOfStock:
        await callback.answer(t("catalog.out_of_stock"), show_alert=True)
        return
    await session.commit()
    await callback.answer(t("cart.added"))


async def cart_text(session: AsyncSession, items: list[CartItem]) -> str:
    titles = dict(
        (
            await session.execute(
                select(Product.id, Product.title_fa).where(
                    Product.id.in_([item.product_id for item in items])
                )
            )
        ).all()
    )
    lines = [
        t(
            "cart.line",
            title=titles.get(item.product_id, f"#{item.product_id}"),
            qty=fa_digits(item.qty),
            unit=money_rial(item.price_at_add_rial),
            line=money_rial(item.qty * item.price_at_add_rial),
            controls="",
        )
        for item in items
    ]
    return "\n\n".join(lines) + "\n\n" + t("cart.total", total=money_rial(subtotal(items)))


async def render_cart(message: Message, session: AsyncSession, user: User | None) -> None:
    if not await allow_message(message, user) or user is None:
        return
    cart = await get_or_create_cart(session, user.id)
    items = await list_items(session, cart.id)
    if not items:
        await message.answer(t("cart.empty"))
        return
    await message.answer(await cart_text(session, items), reply_markup=cart_keyboard(items))


@router.message(F.text == t("menu.cart"))
async def cart_button(message: Message, session: AsyncSession, user: User | None) -> None:
    await render_cart(message, session, user)


async def _edit_cart(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    cart = await get_or_create_cart(session, user.id)
    items = await list_items(session, cart.id)
    if not items:
        await _edit(callback, t("cart.empty"))
        return
    await _edit(callback, await cart_text(session, items), cart_keyboard(items))


@router.callback_query(F.data.startswith("q:"))
async def qty_callback(callback: CallbackQuery, session: AsyncSession, user: User | None) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    _, raw_item, raw_delta = _data(callback).split(":")
    cart = await get_or_create_cart(session, user.id)
    item = next((i for i in await list_items(session, cart.id) if i.id == int(raw_item)), None)
    if item is None:
        await callback.answer(t("cart.not_found"), show_alert=True)
        return
    try:
        changed = await set_qty(session, cart.id, item.id, item.qty + int(raw_delta))
    except (OutOfStock, TooMany):
        await callback.answer(t("cart.stock_limit", limit=20), show_alert=True)
        return
    if changed is None:
        await callback.answer(t("cart.not_found"), show_alert=True)
        return
    await session.commit()
    await _edit_cart(callback, session, user)
    await callback.answer(t("cart.updated"))


@router.callback_query(F.data.startswith("d:"))
async def remove_callback(
    callback: CallbackQuery, session: AsyncSession, user: User | None
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    cart = await get_or_create_cart(session, user.id)
    if not await remove_item(session, cart.id, int(_data(callback).split(":")[1])):
        await callback.answer(t("cart.not_found"), show_alert=True)
        return
    await session.commit()
    await _edit_cart(callback, session, user)
    await callback.answer(t("cart.removed"))


@router.callback_query(F.data == "cc")
async def clear_callback(callback: CallbackQuery, session: AsyncSession, user: User | None) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    cart = await get_or_create_cart(session, user.id)
    await clear(session, cart.id)
    await session.commit()
    await _edit(callback, t("cart.cleared"))
    await callback.answer()
