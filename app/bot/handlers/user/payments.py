"""Customer payment flows: wallet, card-to-card, mixed and wallet top-up."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.guards import allow_callback, allow_message
from app.bot.handlers.user.orders import _order_details
from app.bot.keyboards.inline import (
    fulfillment_keyboard,
    payment_intent_keyboard,
    payment_method_keyboard,
    wallet_keyboard,
)
from app.bot.keyboards.reply import remove_keyboard
from app.bot.states import PaymentFlow, Topup
from app.config import Settings
from app.db.models import Order, User
from app.i18n import money_rial, t
from app.services.notifications import notify_admins, notify_user
from app.services.payments import (
    attach_proof,
    create_intent,
    expire_stale,
    get_intent,
    intent_display,
    pay_order_from_wallet,
)
from app.services.wallet import history

router = Router(name="payments")


def _data(callback: CallbackQuery) -> str:
    return callback.data or ""


async def _payment_menu(
    callback: CallbackQuery, session: AsyncSession, user: User, order: Order
) -> None:
    wallet = await session.get(User, user.id)
    balance = wallet.wallet_balance_rial if wallet else 0
    remaining = order.total_rial - order.wallet_paid_rial - order.card_paid_rial
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("pay.method_title", total=money_rial(remaining), balance=money_rial(balance)),
            reply_markup=payment_method_keyboard(order.id, balance, remaining),
        )


@router.callback_query(F.data.startswith("pay:"))
async def payment_entry(
    callback: CallbackQuery, session: AsyncSession, user: User | None
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    order = await session.get(Order, int(_data(callback).split(":")[1]))
    if order is None or order.user_id != user.id:
        await callback.answer(t("orders.gone"), show_alert=True)
        return
    if order.status in ("paid", "delivered", "shipped", "cancelled"):
        await callback.answer(t("pay.paid"), show_alert=True)
        return
    await _payment_menu(callback, session, user, order)
    await callback.answer()


@router.callback_query(F.data.startswith("pm:wallet:"))
async def pay_wallet(
    callback: CallbackQuery, session: AsyncSession, user: User | None, bot: Bot, settings: Settings
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    order = await session.get(Order, int(_data(callback).split(":")[2]))
    if order is None or order.user_id != user.id:
        await callback.answer(t("orders.gone"), show_alert=True)
        return
    used = await pay_order_from_wallet(session, order, user.id, actor=user.telegram_id)
    if used == 0:
        await callback.answer(t("pay.insufficient"), show_alert=True)
        return
    await session.commit()
    remaining = order.total_rial - order.wallet_paid_rial - order.card_paid_rial
    if remaining == 0:
        await notify_user(bot, session, user, t("pay.paid"))
        await notify_admins(
            bot,
            settings,
            await _order_details(session, order),
            reply_markup=fulfillment_keyboard(order.id),
        )
        await session.commit()
        await _edit(callback, t("pay.paid"))
    else:
        await _edit(callback, t("pay.partial"))
        await _payment_menu(callback, session, user, order)
    await callback.answer()


@router.callback_query(F.data.startswith("pm:mixed:"))
async def pay_mixed(
    callback: CallbackQuery, session: AsyncSession, user: User | None, settings: Settings
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    order = await session.get(Order, int(_data(callback).split(":")[2]))
    if order is None or order.user_id != user.id:
        await callback.answer(t("orders.gone"), show_alert=True)
        return
    await pay_order_from_wallet(session, order, user.id, actor=user.telegram_id)
    await session.commit()
    await _start_card_intent(callback, session, user, order, settings=settings)


async def _start_card_intent(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    order: Order | None,
    *,
    settings: Settings | None,
) -> None:
    from app.config import get_settings

    settings = settings or get_settings()
    amount = (
        order.total_rial - order.wallet_paid_rial - order.card_paid_rial
        if order is not None
        else 0
    )
    if amount <= 0:
        await callback.answer(t("pay.paid"), show_alert=True)
        return
    intent = await create_intent(
        session,
        user_id=user.id,
        amount_rial=amount,
        purpose="order" if order is not None else "wallet_topup",
        settings=settings,
        order_id=order.id if order is not None else None,
    )
    await session.commit()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            intent_display(intent, settings), reply_markup=payment_intent_keyboard(intent.id)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("pm:card:"))
async def pay_card(
    callback: CallbackQuery, session: AsyncSession, user: User | None, settings: Settings
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    order = await session.get(Order, int(_data(callback).split(":")[2]))
    if order is None or order.user_id != user.id:
        await callback.answer(t("orders.gone"), show_alert=True)
        return
    await _start_card_intent(callback, session, user, order, settings=settings)


@router.callback_query(F.data.startswith("pi:status:"))
async def intent_status(
    callback: CallbackQuery, session: AsyncSession, user: User | None, bot: Bot, settings: Settings
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    await expire_stale(session)
    await session.commit()
    intent = await get_intent(session, int(_data(callback).split(":")[2]))
    if intent is None or intent.user_id != user.id:
        await callback.answer(t("pay.intent_not_found"), show_alert=True)
        return
    if intent.status == "matched":
        await callback.answer(t("pay.paid"), show_alert=True)
        order = await session.get(Order, intent.order_id) if intent.order_id else None
        if order is not None:
            await notify_admins(
            bot,
            settings,
            await _order_details(session, order),
            reply_markup=fulfillment_keyboard(order.id),
        )
            await session.commit()
    elif intent.status == "expired":
        await callback.answer(t("pay.intent_expired"), show_alert=True)
    else:
        await callback.answer(t("pay.partial"), show_alert=True)


@router.callback_query(F.data.startswith("pi:receipt:"))
async def receipt_start(
    callback: CallbackQuery, session: AsyncSession, user: User | None, state: FSMContext
) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    intent = await get_intent(session, int(_data(callback).split(":")[2]))
    if intent is None or intent.user_id != user.id:
        await callback.answer(t("pay.intent_not_found"), show_alert=True)
        return
    await state.update_data(intent_id=intent.id)
    await state.set_state(PaymentFlow.receipt)
    if isinstance(callback.message, Message):
        await callback.message.answer(t("pay.receipt_ask"), reply_markup=remove_keyboard())
    await callback.answer()


@router.message(PaymentFlow.receipt, F.photo)
async def receipt_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User | None,
    bot: Bot,
    settings: Settings,
) -> None:
    if user is None or message.photo is None:
        await message.answer(t("pay.receipt_invalid"))
        return
    data = await state.get_data()
    intent = await get_intent(session, int(data.get("intent_id", 0)))
    if intent is None or intent.user_id != user.id:
        await state.clear()
        await message.answer(t("pay.intent_not_found"))
        return
    proof = await attach_proof(
        session, intent, file_id=message.photo[-1].file_id, message_id=message.message_id
    )
    await session.commit()
    await state.clear()
    await message.answer(t("pay.receipt_saved"))
    await notify_admins(
        bot,
        settings,
        t(
            "admin.proof_line",
            id=proof.id,
            user_id=user.telegram_id,
            amount=intent.expected_amount_rial,
        ),
    )


@router.message(F.text == t("menu.wallet"))
async def wallet_menu(message: Message, session: AsyncSession, user: User | None) -> None:
    if not await allow_message(message, user) or user is None:
        return
    await message.answer(
        t("wallet.title", balance=money_rial(user.wallet_balance_rial)),
        reply_markup=wallet_keyboard(),
    )


@router.callback_query(F.data == "wal:topup")
async def wallet_topup_start(callback: CallbackQuery, state: FSMContext, user: User | None) -> None:
    if not await allow_callback(callback, user):
        return
    await state.set_state(Topup.amount)
    if isinstance(callback.message, Message):
        await callback.message.answer(t("wallet.topup_ask"), reply_markup=remove_keyboard())
    await callback.answer()


@router.message(Topup.amount, F.text)
async def wallet_topup_amount(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User | None,
    settings: Settings,
) -> None:
    from app.utils.digits import to_ascii_digits

    if user is None:
        await state.clear()
        return
    raw = to_ascii_digits((message.text or "").strip()).replace(",", "")
    try:
        toman = int(raw)
    except ValueError:
        await message.answer(t("wallet.topup_invalid"))
        return
    if toman < 100:
        await message.answer(t("wallet.topup_invalid"))
        return

    class _FakeCallback:
        def __init__(self, message: Message) -> None:
            self.message = message

        async def answer(self, *args: object, **kwargs: object) -> None:
            return None

    await _start_card_intent(
        _FakeCallback(message),  # type: ignore[arg-type]
        session,
        user,
        None,
        settings=settings,
    )
    await state.clear()


@router.callback_query(F.data == "wal:history")
async def wallet_history(callback: CallbackQuery, session: AsyncSession, user: User | None) -> None:
    if not await allow_callback(callback, user) or user is None:
        return
    rows = await history(session, user.id)
    if not rows:
        text = t("wallet.empty_history")
    else:
        text = "\n".join(
            t(
                "wallet.tx_line",
                type=tx.type,
                amount=money_rial(abs(tx.amount_rial)),
                balance=money_rial(tx.balance_after_rial),
            )
            for tx in rows
        )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
    await callback.answer()


async def _edit(callback: CallbackQuery, text: str) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
