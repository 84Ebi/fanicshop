"""Admin: product CRUD, order management and wallet adjustments."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.user.orders import _order_details
from app.bot.keyboards.inline import paged_list_keyboard
from app.bot.states import AdminOrderLocation, AdminOrderRefund, AdminOrderSearch, AdminProduct
from app.db.models import Order, User
from app.i18n import fa_digits, money_rial, t
from app.services.catalog import (
    archive_product,
    create_category,
    create_product,
    get_product,
    list_categories,
    list_products,
    set_price,
    set_stock,
)
from app.services.notifications import notify_user
from app.services.orders import count_orders_admin, list_orders_admin, set_order_status
from app.services.wallet import admin_adjust

router = Router(name="admin_shop")


def _data(callback: CallbackQuery) -> str:
    return callback.data or ""


def _text(message: Message) -> str:
    return message.text or ""


def _admin_amount(raw: str) -> int | None:
    digits = fa_digits(raw) if any(ch in raw for ch in "۰۱۲۳۴۵۶۷۸۹") else raw
    try:
        return int(digits.replace(",", ""))
    except ValueError:
        return None


def _categories_markup(categories: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=cat.title_fa, callback_data=f"ap:cat:{cat.id}")]
        for cat in categories
    ]
    rows.append([InlineKeyboardButton(text=t("admin.new_category"), callback_data="ap:newcat")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cat_products_markup(category_id: int, products: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=p.title_fa, callback_data=f"ap:edit:{p.id}")] for p in products
    ]
    rows.append(
        [InlineKeyboardButton(text=t("admin.new_product"), callback_data=f"ap:new:{category_id}")]
    )
    rows.append([InlineKeyboardButton(text=t("common.back"), callback_data="ap:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _product_markup(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("admin.edit_price"), callback_data=f"ap:price:{product_id}"
                ),
                InlineKeyboardButton(
                    text=t("admin.edit_stock"), callback_data=f"ap:stock:{product_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("admin.archive"), callback_data=f"ap:archive:{product_id}"
                )
            ],
            [InlineKeyboardButton(text=t("common.back"), callback_data="ap:menu")],
        ]
    )


def _order_filter_markup() -> InlineKeyboardMarkup:
    statuses = [
        "awaiting_payment",
        "paid",
        "preparing",
        "shipped",
        "out_for_delivery",
        "delivered",
        "cancelled",
    ]
    rows = [
        [InlineKeyboardButton(text=t("admin.order_filter_all"), callback_data="ao:list:all:0")]
    ]
    rows += [
        [
            InlineKeyboardButton(
                text=t(f"orders.status.{status}"), callback_data=f"ao:list:{status}:0"
            )
        ]
        for status in statuses
    ]
    rows.append([InlineKeyboardButton(text=t("admin.order_search"), callback_data="ao:search")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("products"))
async def products_command(message: Message, session: AsyncSession) -> None:
    categories = await list_categories(session)
    if not categories:
        await message.answer(t("admin.no_categories"), reply_markup=_categories_markup([]))
        return
    await message.answer(t("admin.products_title"), reply_markup=_categories_markup(categories))


@router.callback_query(F.data == "ap:menu")
async def products_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    categories = await list_categories(session)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("admin.products_title"), reply_markup=_categories_markup(categories)
        )
    await callback.answer()


@router.callback_query(F.data == "ap:newcat")
async def new_category(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminProduct.category_slug)
    if isinstance(callback.message, Message):
        await callback.message.answer(t("admin.cat_slug_ask"))
    await callback.answer()


@router.message(AdminProduct.category_slug, F.text)
async def category_slug(message: Message, state: FSMContext) -> None:
    slug = "".join(ch for ch in _text(message).strip().lower() if ch.isalnum() or ch in "-_")
    if not slug:
        await message.answer(t("admin.cat_slug_ask"))
        return
    await state.update_data(slug=slug)
    await state.set_state(AdminProduct.category_title)
    await message.answer(t("admin.cat_title_ask"))


@router.message(AdminProduct.category_title, F.text)
async def category_title(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await create_category(session, slug=data["slug"], title_fa=_text(message))
    await session.commit()
    await state.clear()
    await message.answer(t("admin.cat_created"))


@router.callback_query(F.data.startswith("ap:cat:"))
async def category_products(callback: CallbackQuery, session: AsyncSession) -> None:
    category_id = int(_data(callback).split(":")[2])
    products = await list_products(session, category_id)
    rows = "\n".join(f"• {p.title_fa} — {money_rial(p.price_rial)}" for p in products)
    text = t("admin.products_in_cat", rows=rows or t("admin.no_products"))
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text, reply_markup=_cat_products_markup(category_id, products)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("ap:new:"))
async def new_product(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(category_id=int(_data(callback).split(":")[2]))
    await state.set_state(AdminProduct.title)
    if isinstance(callback.message, Message):
        await callback.message.answer(t("admin.product_title_ask"))
    await callback.answer()


@router.message(AdminProduct.title, F.text)
async def product_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=_text(message).strip())
    await state.set_state(AdminProduct.description)
    await message.answer(t("admin.product_desc_ask"))


@router.message(AdminProduct.description, F.text)
async def product_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=_text(message).strip())
    await state.set_state(AdminProduct.price)
    await message.answer(t("admin.product_price_ask"))


@router.message(AdminProduct.price, F.text)
async def product_price(message: Message, state: FSMContext) -> None:
    amount = _admin_amount(_text(message))
    if amount is None or amount <= 0:
        await message.answer(t("admin.invalid_amount"))
        return
    await state.update_data(price_rial=amount * 10)
    await state.set_state(AdminProduct.stock)
    await message.answer(t("admin.product_stock_ask"))


@router.message(AdminProduct.stock, F.text)
async def product_stock(message: Message, state: FSMContext) -> None:
    stock = _admin_amount(_text(message))
    if stock is None or not 0 <= stock <= 10_000:
        await message.answer(t("admin.invalid_stock"))
        return
    await state.update_data(stock=stock)
    await state.set_state(AdminProduct.photo)
    await message.answer(t("admin.product_photo_ask"))


@router.message(AdminProduct.photo)
async def product_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    file_id = (
        message.photo[-1].file_id
        if message.photo and _text(message) != t("common.skip")
        else None
    )
    await create_product(
        session,
        category_id=int(data["category_id"]),
        title_fa=data["title"],
        description_fa=data.get("description"),
        price_rial=int(data["price_rial"]),
        stock_qty=int(data["stock"]),
        photo_file_id=file_id,
    )
    await session.commit()
    await state.clear()
    await message.answer(t("admin.product_created"))


@router.callback_query(F.data.startswith("ap:edit:"))
async def edit_product(callback: CallbackQuery, session: AsyncSession) -> None:
    product = await get_product(session, int(_data(callback).split(":")[2]))
    if product is None:
        await callback.answer(t("admin.not_found"), show_alert=True)
        return
    text = f"{product.title_fa}\n💰 {money_rial(product.price_rial)}\n📦 {product.stock_qty}"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=_product_markup(product.id))
    await callback.answer()


@router.callback_query(F.data.startswith("ap:price:"))
async def edit_price_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(product_id=int(_data(callback).split(":")[2]))
    await state.set_state(AdminProduct.new_price)
    if isinstance(callback.message, Message):
        await callback.message.answer(t("admin.value_ask"))
    await callback.answer()


@router.message(AdminProduct.new_price, F.text)
async def edit_price(message: Message, state: FSMContext, session: AsyncSession) -> None:
    amount = _admin_amount(_text(message))
    if amount is None or amount <= 0:
        await message.answer(t("admin.invalid_amount"))
        return
    data = await state.get_data()
    product = await get_product(session, int(data["product_id"]))
    if product is None:
        await state.clear()
        return
    await set_price(session, product, amount * 10)
    await session.commit()
    await state.clear()
    await message.answer(t("admin.value_saved"))


@router.callback_query(F.data.startswith("ap:stock:"))
async def edit_stock_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(product_id=int(_data(callback).split(":")[2]))
    await state.set_state(AdminProduct.new_stock)
    if isinstance(callback.message, Message):
        await callback.message.answer(t("admin.value_ask"))
    await callback.answer()


@router.message(AdminProduct.new_stock, F.text)
async def edit_stock(message: Message, state: FSMContext, session: AsyncSession) -> None:
    stock = _admin_amount(_text(message))
    if stock is None or not 0 <= stock <= 10_000:
        await message.answer(t("admin.invalid_stock"))
        return
    data = await state.get_data()
    product = await get_product(session, int(data["product_id"]))
    if product is None:
        await state.clear()
        return
    try:
        await set_stock(session, product, stock)
    except ValueError:
        await message.answer(t("admin.invalid_stock"))
        return
    await session.commit()
    await state.clear()
    await message.answer(t("admin.value_saved"))


@router.callback_query(F.data.startswith("ap:archive:"))
async def archive(callback: CallbackQuery, session: AsyncSession) -> None:
    product = await get_product(session, int(_data(callback).split(":")[2]))
    if product is None:
        await callback.answer(t("admin.not_found"), show_alert=True)
        return
    await archive_product(session, product)
    await session.commit()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(t("admin.archived"))
    await callback.answer(t("admin.archived"))


@router.message(Command("orders"))
async def orders_command(message: Message) -> None:
    await message.answer(t("admin.orders_title"), reply_markup=_order_filter_markup())


async def _render_order_list(
    callback: CallbackQuery,
    session: AsyncSession,
    *,
    status: str,
    search: str | None,
    page: int,
) -> None:
    orders = await list_orders_admin(
        session,
        status=status,
        search=search,
        limit=8,
        offset=page * 8,
    )
    total = await count_orders_admin(session, status=status, search=search)
    has_next = (page + 1) * 8 < total
    items = [
        (
            t(
                "admin.order_line",
                code=o.public_code,
                status=t(f"orders.status.{o.status}"),
                total=money_rial(o.total_rial),
            ),
            f"ao:view:{o.id}",
        )
        for o in orders
    ]
    prefix = f"ao:list:{status}:"
    if search:
        text = t("admin.order_search_results") + f" ({total})"
    else:
        text = t("admin.orders_title") + f" ({total})"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text if items else t("orders.empty"),
            reply_markup=paged_list_keyboard(
                items, page=page, has_next=has_next, prefix=prefix, back_cb="adm:goto:orders"
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("ao:list:"))
async def orders_list(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, status, page_str = _data(callback).split(":")
    await _render_order_list(
        callback, session, status=status, search=None, page=int(page_str)
    )


@router.callback_query(F.data == "ao:search")
async def orders_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminOrderSearch.query)
    if isinstance(callback.message, Message):
        await callback.message.answer(t("admin.order_search_ask"))
    await callback.answer()


@router.message(AdminOrderSearch.query, F.text)
async def orders_search(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    await state.clear()
    orders = await list_orders_admin(session, status="all", search=text, limit=8)
    if not orders:
        await message.answer(t("orders.empty"), reply_markup=_order_filter_markup())
        return
    rows = "\n".join(
        t(
            "admin.order_line",
            code=o.public_code,
            status=t(f"orders.status.{o.status}"),
            total=money_rial(o.total_rial),
        )
        for o in orders
    )
    await message.answer(t("admin.order_search_results") + f"\n{rows}")


@router.callback_query(F.data.startswith("ao:view:"))
async def admin_order_view(callback: CallbackQuery, session: AsyncSession) -> None:
    order = await session.get(Order, int(_data(callback).split(":")[2]))
    if order is None:
        await callback.answer(t("orders.gone"), show_alert=True)
        return
    buttons = [
        InlineKeyboardButton(
            text=t(f"orders.status.{status}"), callback_data=f"aos:{order.id}:{status}"
        )
        for status in ("preparing", "shipped", "out_for_delivery", "delivered", "cancelled")
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append(
        [
            InlineKeyboardButton(
                text=t("admin.order_send_location"), callback_data=f"ao:loc:{order.id}"
            )
        ]
    )
    if order.status in ("awaiting_payment", "paid"):
        rows.append(
            [
                InlineKeyboardButton(
                    text=t("admin.order_refund"), callback_data=f"aos:refund:{order.id}"
                )
            ]
        )
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(await _order_details(session, order), reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("aos:refund:"))
async def admin_order_refund_start(
    callback: CallbackQuery, state: FSMContext
) -> None:
    order_id = int(_data(callback).split(":")[2])
    await state.set_state(AdminOrderRefund.reason)
    await state.update_data(order_id=order_id)
    if isinstance(callback.message, Message):
        await callback.message.answer(t("admin.refund_ask"))
    await callback.answer()


@router.message(AdminOrderRefund.reason, F.text)
async def admin_order_refund(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    await state.clear()
    order = await session.get(Order, int(data.get("order_id", 0)))
    if order is None:
        await message.answer(t("orders.gone"))
        return
    await admin_adjust(
        session,
        user_id=order.user_id,
        amount_rial=order.total_rial,
        reason=("refund " + order.public_code + " — " + (message.text or "")[:200]),
        actor_telegram_id=message.from_user.id,
    )
    await session.commit()
    user = await session.get(User, order.user_id)
    if user is not None:
        await notify_user(bot, session, user, t("notify.refunded", code=order.public_code))
    await message.answer(t("admin.refund_done"))


@router.callback_query(F.data.startswith("ao:loc:"))
async def admin_send_location_start(
    callback: CallbackQuery, state: FSMContext
) -> None:
    raw_id = _data(callback).split(":")[2]
    await state.set_state(AdminOrderLocation.location)
    await state.update_data(order_id=int(raw_id))
    if isinstance(callback.message, Message):
        await callback.message.answer(t("admin.location_ask"))
    await callback.answer()


@router.message(AdminOrderLocation.location, F.location)
async def admin_send_location(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    if message.from_user is None or message.location is None:
        return
    data = await state.get_data()
    order = await session.get(Order, int(data.get("order_id", 0)))
    if order is None:
        await message.answer(t("orders.gone"))
        await state.clear()
        return
    loc = message.location
    order.delivery_location = {"latitude": loc.latitude, "longitude": loc.longitude}
    if order.status in ("awaiting_payment", "paid"):
        await set_order_status(session, order, "preparing", actor_telegram_id=message.from_user.id)
    await session.commit()
    await state.clear()
    user = await session.get(User, order.user_id)
    if user is not None:
        try:
            await bot.send_message(user.telegram_id, t("notify.order_verified"))
            await bot.send_location(user.telegram_id, loc.latitude, loc.longitude)
        except Exception as exc:  # best-effort; never fail the admin action
            from app.logging import get_logger

            get_logger("admin_shop").warning("location_notify_failed", error=str(exc))
    await message.answer(t("admin.location_saved"))


@router.callback_query(F.data.startswith("aos:"))
async def admin_order_status(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
) -> None:
    _, raw_id, status = _data(callback).split(":")
    order = await session.get(Order, int(raw_id))
    if order is None:
        await callback.answer(t("orders.gone"), show_alert=True)
        return
    if not await set_order_status(session, order, status, actor_telegram_id=callback.from_user.id):
        await callback.answer(t("admin.invalid_state"), show_alert=True)
        return
    await session.commit()
    user = await session.get(User, order.user_id)
    if user is not None:
        await notify_user(
            bot,
            session,
            user,
            t("notify.order_status", status=t(f"orders.status.{status}")),
        )
        await session.commit()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(await _order_details(session, order))
    await callback.answer(t("admin.status_updated"))


@router.callback_query(F.data.startswith("adm:fulfill:"))
@router.callback_query(F.data.startswith("adm:ship:"))
async def fulfillment_button(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
) -> None:
    _, action, raw_id = _data(callback).split(":")
    order = await session.get(Order, int(raw_id))
    if order is None:
        await callback.answer(t("orders.gone"), show_alert=True)
        return
    status = "delivered" if action == "fulfill" else "shipped"
    if not await set_order_status(session, order, status, actor_telegram_id=callback.from_user.id):
        await callback.answer(t("admin.invalid_state"), show_alert=True)
        return
    await session.commit()
    user = await session.get(User, order.user_id)
    if user is not None:
        from app.bot.keyboards.inline import receipt_confirm_keyboard

        await bot.send_message(
            user.telegram_id,
            t("notify.delivered_ask"),
            reply_markup=receipt_confirm_keyboard(order.id),
        )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(await _order_details(session, order))
    await callback.answer(t("admin.status_updated"))


@router.message(Command("credit"))
async def credit_command(message: Message, session: AsyncSession) -> None:
    parts = _text(message).split()
    if len(parts) < 4:
        await message.answer(t("admin.credit_usage"))
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer(t("admin.invalid_user"))
        return
    user = await session.get(User, user_id)
    amount = _admin_amount(parts[2])
    if user is None:
        await message.answer(t("admin.invalid_user"))
        return
    if amount is None or amount == 0:
        await message.answer(t("admin.invalid_amount"))
        return
    assert user is not None
    if message.from_user is None:
        return
    await admin_adjust(
        session,
        user_id=user.id,
        amount_rial=amount * 10,
        reason=" ".join(parts[3:])[:300],
        actor_telegram_id=message.from_user.id,
    )
    await session.commit()
    await message.answer(t("admin.credit_done"))


@router.callback_query(F.data == "adm:goto:products")
async def goto_products(callback: CallbackQuery, session: AsyncSession) -> None:
    await products_menu(callback, session)


@router.callback_query(F.data == "adm:goto:orders")
async def goto_orders(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("admin.orders_title"), reply_markup=_order_filter_markup()
        )
    await callback.answer()
