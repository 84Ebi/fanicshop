"""Inline keyboards and callback-data builders.

Callback format (≤64 bytes):
    age:yes | age:no
    su:ok | su:edit
    adm:panel
    adm:pending:<page>
    adm:users
    adm:u:view:<user_id>
    adm:u:ok:<user_id> | adm:u:no:<user_id> | adm:u:blk:<user_id> | adm:u:unb:<user_id>
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Address, CartItem, Category, Order, Product, User
from app.i18n import t


def age_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("common.yes"), callback_data="age:yes"),
                InlineKeyboardButton(text=t("common.no"), callback_data="age:no"),
            ]
        ]
    )


def signup_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("common.confirm"), callback_data="su:ok"),
                InlineKeyboardButton(text=t("common.edit"), callback_data="su:edit"),
            ]
        ]
    )


def signup_admin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("admin.approve"), callback_data=f"adm:u:ok:{user_id}"),
                InlineKeyboardButton(text=t("admin.reject"), callback_data=f"adm:u:no:{user_id}"),
            ],
            [
                InlineKeyboardButton(text=t("admin.block"), callback_data=f"adm:u:blk:{user_id}"),
                InlineKeyboardButton(
                    text=t("admin.view"),
                    callback_data=f"adm:u:view:{user_id}",
                ),
            ],
        ]
    )


def admin_panel_keyboard(pending_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("admin.pending", count=pending_count),
                    callback_data="adm:pending:0",
                )
            ],
            [InlineKeyboardButton(text=t("admin.users"), callback_data="adm:users")],
        ]
    )


def admin_user_keyboard(user: User) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if user.status == "pending":
        rows.append(
            [
                InlineKeyboardButton(text=t("admin.approve"), callback_data=f"adm:u:ok:{user.id}"),
                InlineKeyboardButton(text=t("admin.reject"), callback_data=f"adm:u:no:{user.id}"),
            ]
        )
    if user.status == "blocked":
        rows.append(
            [InlineKeyboardButton(text=t("admin.unblock"), callback_data=f"adm:u:unb:{user.id}")]
        )
    else:
        rows.append(
            [InlineKeyboardButton(text=t("admin.block"), callback_data=f"adm:u:blk:{user.id}")]
        )
    rows.append([InlineKeyboardButton(text=t("common.back"), callback_data="adm:pending:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pending_list_keyboard(users: list[User], page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{u.full_name} — {u.phone}",
                callback_data=f"adm:u:view:{u.id}",
            )
        ]
        for u in users
    ]
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm:pending:{page - 1}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm:pending:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text=t("common.back"), callback_data="adm:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_results_keyboard(users: list[User]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{u.full_name} — {u.phone or '-'}",
                callback_data=f"adm:u:view:{u.id}",
            )
        ]
        for u in users
    ]
    rows.append([InlineKeyboardButton(text=t("common.back"), callback_data="adm:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("common.back"), callback_data="adm:panel")]]
    )


# ── Catalog & cart ──────────────────────────────────────────────────────────


def categories_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=cat.title_fa, callback_data=f"cat:{cat.id}")]
        for cat in categories
    ]
    return (
        InlineKeyboardMarkup(inline_keyboard=rows)
        if rows
        else InlineKeyboardMarkup(inline_keyboard=[])
    )


def products_keyboard(products: list[Product], category_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=p.title_fa, callback_data=f"p:{p.id}")]
        for p in products
        if (p.stock_qty - p.reserved_qty) > 0
    ]
    rows.append([InlineKeyboardButton(text=t("catalog.back_categories"), callback_data="cats")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_keyboard(product: Product) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if (product.stock_qty - product.reserved_qty) > 0:
        rows.append(
            [InlineKeyboardButton(text=t("catalog.add"), callback_data=f"a:{product.id}")]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=t("catalog.back_products"), callback_data=f"cat:{product.category_id}"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def address_keyboard(addresses: list[Address]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{a.province} - {a.city} - {a.address_line[:24]}",
                callback_data=f"addr:{a.id}",
            )
        ]
        for a in addresses
    ]
    rows.append([InlineKeyboardButton(text=t("checkout.new_address"), callback_data="addr:new")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def checkout_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("checkout.place_order"), callback_data="co:ok"),
                InlineKeyboardButton(text=t("common.cancel"), callback_data="co:cancel"),
            ]
        ]
    )


def orders_keyboard(orders: list[Order]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{o.public_code}", callback_data=f"o:{o.id}")]
        for o in orders
    ]
    return (
        InlineKeyboardMarkup(inline_keyboard=rows)
        if rows
        else InlineKeyboardMarkup(inline_keyboard=[])
    )


def order_keyboard(order: Order) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if order.status == "awaiting_payment":
        rows.append(
            [InlineKeyboardButton(text="💳 پرداخت", callback_data=f"pay:{order.id}")]
        )
        rows.append(
            [InlineKeyboardButton(text=t("orders.cancel"), callback_data=f"oc:{order.id}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_keyboard(items: list[CartItem]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        rows.append(
            [
                InlineKeyboardButton(text=t("cart.minus"), callback_data=f"q:{item.id}:-1"),
                InlineKeyboardButton(text=str(item.qty), callback_data="noop"),
                InlineKeyboardButton(text=t("cart.plus"), callback_data=f"q:{item.id}:1"),
                InlineKeyboardButton(text=t("cart.remove"), callback_data=f"d:{item.id}"),
            ]
        )
    if items:
        rows.append([InlineKeyboardButton(text=t("cart.checkout"), callback_data="checkout")])
        rows.append([InlineKeyboardButton(text=t("cart.clear"), callback_data="cc")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
