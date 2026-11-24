"""Identity: users + append-only audit events."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin

USER_STATUSES = ("draft", "pending", "verified", "rejected", "blocked")
USER_EVENTS = (
    "signup",
    "age_confirm",
    "submitted",
    "approve",
    "reject",
    "block",
    "unblock",
    "phone_change",
)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    tg_first_name: Mapped[str | None] = mapped_column(String(128))
    tg_last_name: Mapped[str | None] = mapped_column(String(128))
    full_name: Mapped[str] = mapped_column(String(60), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(10))
    age_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    block_reason: Mapped[str | None] = mapped_column(Text)
    wallet_balance_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    bot_blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    events: Mapped[list[UserEvent]] = relationship(
        back_populates="user", order_by="UserEvent.id", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("wallet_balance_rial >= 0", name="wallet_nonneg"),
        CheckConstraint(
            f"status IN ({','.join(f"'{s}'" for s in USER_STATUSES)})", name="status_valid"
        ),
        Index(
            "ix_users_phone_partial",
            "phone",
            unique=True,
            postgresql_where=text("phone IS NOT NULL"),
        ),
    )


class UserEvent(CreatedAtMixin, Base):
    __tablename__ = "user_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event: Mapped[str] = mapped_column(String(24), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str | None] = mapped_column(String(16))
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="events")

    __table_args__ = (
        CheckConstraint(
            f"event IN ({','.join(f"'{e}'" for e in USER_EVENTS)})", name="event_valid"
        ),
    )


class Address(TimestampMixin, Base):
    """Saved shipping address (soft-deleted rows keep FK integrity)."""

    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    receiver_name: Mapped[str] = mapped_column(String(60), nullable=False)
    receiver_phone: Mapped[str] = mapped_column(String(10), nullable=False)
    province: Mapped[str] = mapped_column(String(60), nullable=False)
    city: Mapped[str] = mapped_column(String(60), nullable=False)
    address_line: Mapped[str] = mapped_column(String(300), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(10))
    note: Mapped[str | None] = mapped_column(String(300))
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)

    __table_args__ = (
        Index(
            "ix_addresses_default_partial",
            "user_id",
            unique=True,
            postgresql_where=text("is_default AND NOT is_deleted"),
        ),
    )
