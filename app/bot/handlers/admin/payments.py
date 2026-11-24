"""Admin: manual proof review and payment log."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import proof_keyboard
from app.db.models import PaymentIntent, PaymentProof, User
from app.i18n import money_rial, t
from app.services.notifications import notify_user
from app.services.payments import get_intent, review_proof

router = Router(name="admin_payments")


def _data(callback: CallbackQuery) -> str:
    return callback.data or ""


async def _proof_list(session: AsyncSession) -> tuple[str, list[PaymentProof]]:
    proofs = list(
        await session.scalars(
            select(PaymentProof).where(PaymentProof.status == "pending").order_by(PaymentProof.id)
        )
    )
    if not proofs:
        return t("admin.proof_empty"), []
    lines = []
    for proof in proofs:
        intent = await session.get(PaymentIntent, proof.intent_id)
        lines.append(
            t(
                "admin.proof_line",
                id=proof.id,
                user_id=intent.user_id if intent else "-",
                amount=money_rial(intent.expected_amount_rial) if intent else "-",
            )
        )
    return "\n".join(lines), proofs


@router.message(Command("proofs"))
async def proofs_command(message: Message, session: AsyncSession) -> None:
    text, proofs = await _proof_list(session)
    if proofs:
        await message.answer(text, reply_markup=proof_keyboard(proofs[0].id))
    else:
        await message.answer(text)


@router.callback_query(F.data.startswith("proof:ok:"))
async def approve_proof(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
) -> None:
    proof = await session.get(PaymentProof, int(_data(callback).split(":")[2]))
    if proof is None:
        await callback.answer(t("admin.not_found"), show_alert=True)
        return
    changed = await review_proof(
        session, proof, approve=True, actor=callback.from_user.id
    )
    if not changed:
        await callback.answer(t("admin.invalid_state"), show_alert=True)
        return
    intent = await get_intent(session, proof.intent_id)
    await session.commit()
    if intent is not None:
        user = await session.get(User, intent.user_id)
        if user is not None:
            await notify_user(bot, session, user, t("pay.paid"))
            await session.commit()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(t("admin.proof_approved"))
    await callback.answer(t("admin.proof_approved"))


@router.callback_query(F.data.startswith("proof:no:"))
async def reject_proof(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    proof = await session.get(PaymentProof, int(_data(callback).split(":")[2]))
    if proof is None:
        await callback.answer(t("admin.not_found"), show_alert=True)
        return
    if not await review_proof(
        session, proof, approve=False, actor=callback.from_user.id
    ):
        await callback.answer(t("admin.invalid_state"), show_alert=True)
        return
    intent = await get_intent(session, proof.intent_id)
    await session.commit()
    if intent is not None:
        user = await session.get(User, intent.user_id)
        if user is not None:
            await notify_user(
                bot, session, user, t("notify.rejected", reason=proof.reject_reason or "-")
            )
            await session.commit()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(t("admin.proof_rejected"))
    await callback.answer(t("admin.proof_rejected"))


@router.message(Command("payments"))
async def payments_log(message: Message, session: AsyncSession) -> None:
    intents = list(
        await session.scalars(
            select(PaymentIntent).order_by(PaymentIntent.id.desc()).limit(20)
        )
    )
    if not intents:
        await message.answer(t("admin.proof_empty"))
        return
    lines = [
        f"#{i.id} — {i.purpose} — {money_rial(i.expected_amount_rial)} — {i.status}"
        for i in intents
    ]
    await message.answer("\n".join(lines))
