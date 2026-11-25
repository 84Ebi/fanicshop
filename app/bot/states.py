"""FSM states."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Signup(StatesGroup):
    full_name = State()
    phone = State()
    confirm = State()


class PaymentFlow(StatesGroup):
    receipt = State()


class Topup(StatesGroup):
    amount = State()


class Checkout(StatesGroup):
    contact = State()
    confirm = State()


class AdminOrderLocation(StatesGroup):
    location = State()


class AdminBroadcast(StatesGroup):
    text = State()


class AdminOrderSearch(StatesGroup):
    query = State()


class AdminOrderRefund(StatesGroup):
    reason = State()


class SupportFlow(StatesGroup):
    message = State()


class SupportAdminReply(StatesGroup):
    text = State()


class AdminProduct(StatesGroup):
    category_slug = State()
    category_title = State()
    title = State()
    description = State()
    price = State()
    stock = State()
    photo = State()
    new_price = State()
    new_stock = State()


class AdminUserFlow(StatesGroup):
    reject_reason = State()
    block_reason = State()
    search = State()
    message = State()
