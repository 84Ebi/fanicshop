"""Money ledger, audit log, broadcasts, support threads, job outbox, settings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin

WALLET_TX_TYPES = (
    "topup",
    "order_payment",
    "refund",
    "admin_credit",
    "admin_debit",
    "adjustment",
)
BROADCAST_STATUSES = ("draft", "queued", "running", "done", "cancelled", "failed")
BROADCAST_TARGET_STATUSES = ("queued", "sent", "failed", "blocked")
SUPPORT_DIRECTIONS = ("user", "admin")
JOB_STATUSES = ("queued", "running", "done", "failed", "dead")


def _sql_in(values: tuple[str, ...]) -> str:
    return ",".join(f"'{v}'" for v in values)


class WalletTransaction(CreatedAtMixin, Base):
    """Append-only ledger. `users.wallet_balance_rial` must always equal the sum."""

    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        CheckConstraint("amount_rial <> 0", name="amount_nonzero"),
        CheckConstraint("balance_after_rial >= 0", name="balance_after_nonneg"),
        CheckConstraint(f"type IN ({_sql_in(WALLET_TX_TYPES)})", name="type_valid"),
        Index("ix_wallet_tx_user_created", "user_id", "created_at"),
    )


class AdminAuditLog(CreatedAtMixin, Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Broadcast(TimestampMixin, Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str | None] = mapped_column(Text)
    file_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    total_targets: Mapped[int] = mapped_column(default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(default=0, nullable=False)
    blocked_count: Mapped[int] = mapped_column(default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    targets: Mapped[list[BroadcastTarget]] = relationship(
        back_populates="broadcast", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(f"status IN ({_sql_in(BROADCAST_STATUSES)})", name="status_valid"),
    )


class BroadcastTarget(CreatedAtMixin, Base):
    __tablename__ = "broadcast_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(
        ForeignKey("broadcasts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    broadcast: Mapped[Broadcast] = relationship(back_populates="targets")

    __table_args__ = (
        UniqueConstraint("broadcast_id", "user_id", name="uq_broadcast_target"),
        CheckConstraint(f"status IN ({_sql_in(BROADCAST_TARGET_STATUSES)})", name="status_valid"),
    )


class SupportThread(TimestampMixin, Base):
    __tablename__ = "support_threads"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    admin_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    admin_message_id: Mapped[int | None] = mapped_column(BigInteger)
    is_open: Mapped[bool] = mapped_column(default=True, nullable=False)

    messages: Mapped[list[SupportMessage]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="SupportMessage.id"
    )


class SupportMessage(CreatedAtMixin, Base):
    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("support_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    file_id: Mapped[str | None] = mapped_column(String(200))
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)

    thread: Mapped[SupportThread] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint(f"direction IN ({_sql_in(SUPPORT_DIRECTIONS)})", name="direction_valid"),
    )


class Job(TimestampMixin, Base):
    """DB outbox polled by the worker (restart-safe scheduling)."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"status IN ({_sql_in(JOB_STATUSES)})", name="status_valid"),
        CheckConstraint("attempts >= 0", name="attempts_nonneg"),
        Index("ix_jobs_status_run_at", "status", "run_at"),
    )


class Setting(TimestampMixin, Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(BigInteger)
