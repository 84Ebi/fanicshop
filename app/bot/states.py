"""FSM states."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Signup(StatesGroup):
    full_name = State()
    phone = State()
    confirm = State()


class Checkout(StatesGroup):
    address = State()
    note = State()
    confirm = State()


class NewAddress(StatesGroup):
    receiver = State()
    phone = State()
    province = State()
    city = State()
    line = State()
    postal = State()


class AdminUserFlow(StatesGroup):
    reject_reason = State()
    block_reason = State()
    search = State()
