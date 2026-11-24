"""Payments: intents, SMS ingestion, bank transactions, proofs, card bindings."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin

INTENT_PURPOSES = ("order", "wallet_topup")
INTENT_PROVIDERS = ("card_to_card", "gateway")
INTENT_STATUSES = ("pending", "awaiting_review", "matched", "expired", "cancelled")
LIVE_INTENT_STATUSES = ("pending", "awaiting_review")

SMS_PARSE_STATUSES = ("parsed", "unparsed", "ignored")
BANK_TX_STATUSES = ("new", "matched", "unmatched", "ignored", "refunded")
PROOF_STATUSES = ("pending", "approved", "rejected")


def _sql_in(values: tuple[str, ...]) -> str:
    return ",".join(f"'{v}'" for v in values)


class ShopCard(TimestampMixin, Base):
    """Receiving cards. Full PAN lives in env only; this table is last4+mask."""

    __tablename__ = "shop_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank_code: Mapped[str] = mapped_column(String(32), nullable=False)
    card_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    card_masked: Mapped[str] = mapped_column(String(32), nullable=False)
    holder_name_fa: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (Index("uq_shop_cards_bank_last4", "bank_code", "card_last4", unique=True),)


class PaymentIntent(TimestampMixin, Base):
    __tablename__ = "payment_intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(16), default="card_to_card", nullable=False)

    base_amount_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    suffix_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    expected_amount_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    matched_bank_tx_id: Mapped[int | None] = mapped_column(
        ForeignKey("bank_transactions.id", use_alter=True, name="fk_intent_matched_tx"),
        nullable=True,
    )
    attempt_no: Mapped[int] = mapped_column(default=1, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    proofs: Mapped[list[PaymentProof]] = relationship(
        back_populates="intent", cascade="all, delete-orphan", order_by="PaymentProof.id"
    )

    __table_args__ = (
        CheckConstraint(f"purpose IN ({_sql_in(INTENT_PURPOSES)})", name="purpose_valid"),
        CheckConstraint(f"provider IN ({_sql_in(INTENT_PROVIDERS)})", name="provider_valid"),
        CheckConstraint(f"status IN ({_sql_in(INTENT_STATUSES)})", name="status_valid"),
        CheckConstraint("base_amount_rial > 0", name="base_positive"),
        CheckConstraint("suffix_rial >= 0", name="suffix_nonneg"),
        CheckConstraint(
            "expected_amount_rial = base_amount_rial + suffix_rial", name="amount_math"
        ),
        CheckConstraint("attempt_no >= 1", name="attempt_positive"),
        # Two live intents can never share an amount: this is what makes the
        # unique-amount matching ladder sound.
        Index(
            "uq_payment_intents_live_amount",
            "expected_amount_rial",
            unique=True,
            postgresql_where=text("status IN ('pending','awaiting_review')"),
        ),
        # One live intent per order.
        Index(
            "uq_payment_intents_live_order",
            "order_id",
            unique=True,
            postgresql_where=text("purpose = 'order' AND status IN ('pending','awaiting_review')"),
        ),
    )


class SmsMessage(CreatedAtMixin, Base):
    """Raw (card-masked) SMS as received; deduplicated by raw_hash."""

    __tablename__ = "sms_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(24), default="sms_forwarder", nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    sender_number: Mapped[str | None] = mapped_column(String(32))
    bank_code: Mapped[str | None] = mapped_column(String(32))
    parse_status: Mapped[str] = mapped_column(String(16), default="unparsed", nullable=False)
    parse_error: Mapped[str | None] = mapped_column(Text)
    device_id: Mapped[str | None] = mapped_column(String(64))
    remote_ip: Mapped[str | None] = mapped_column(String(45))

    __table_args__ = (
        CheckConstraint(
            f"parse_status IN ({_sql_in(SMS_PARSE_STATUSES)})", name="parse_status_valid"
        ),
    )


class BankTransaction(TimestampMixin, Base):
    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    sms_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("sms_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    bank_code: Mapped[str] = mapped_column(String(32), nullable=False)
    dest_card_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    shop_card_id: Mapped[int | None] = mapped_column(
        ForeignKey("shop_cards.id", ondelete="SET NULL"), nullable=True
    )
    amount_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_card_last4: Mapped[str | None] = mapped_column(String(4))
    sender_name: Mapped[str | None] = mapped_column(String(120))
    ref_number: Mapped[str | None] = mapped_column(String(64))
    transferred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False)
    matched_intent_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_intents.id", ondelete="SET NULL"), nullable=True
    )
    attributed_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("amount_rial > 0", name="amount_positive"),
        CheckConstraint(f"status IN ({_sql_in(BANK_TX_STATUSES)})", name="status_valid"),
        Index(
            "uq_bank_transactions_ref",
            "bank_code",
            "ref_number",
            unique=True,
            postgresql_where=text("ref_number IS NOT NULL"),
        ),
    )


class PaymentProof(TimestampMixin, Base):
    __tablename__ = "payment_proofs"

    id: Mapped[int] = mapped_column(primary_key=True)
    intent_id: Mapped[int] = mapped_column(
        ForeignKey("payment_intents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    telegram_file_id: Mapped[str] = mapped_column(String(200), nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)

    intent: Mapped[PaymentIntent] = relationship(back_populates="proofs")

    __table_args__ = (
        CheckConstraint(f"status IN ({_sql_in(PROOF_STATUSES)})", name="status_valid"),
    )


class CardBinding(TimestampMixin, Base):
    """Learned map: sender card last4 + normalized name → customer."""

    __tablename__ = "card_bindings"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank_code: Mapped[str] = mapped_column(String(32), nullable=False)
    source_card_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    sender_name_norm: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    confidence: Mapped[int] = mapped_column(default=1, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_card_bindings_card_name",
            "bank_code",
            "source_card_last4",
            "sender_name_norm",
            unique=True,
        ),
        CheckConstraint("confidence >= 0", name="confidence_nonneg"),
    )
