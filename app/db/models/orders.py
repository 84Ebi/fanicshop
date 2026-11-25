"""Orders: order, immutable line items, status history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin

ORDER_STATUSES = (
    "awaiting_payment",
    "paid",
    "preparing",
    "shipped",
    "out_for_delivery",
    "delivered",
    "cancelled",
    "refunded",
)
PAYMENT_STATES = ("unpaid", "pending", "partially_paid", "paid", "refunded")
TRANSITION_SOURCES = ("user", "admin", "system")


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="awaiting_payment", nullable=False)
    payment_state: Mapped[str] = mapped_column(String(20), default="unpaid", nullable=False)

    subtotal_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    delivery_fee_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    discount_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    wallet_paid_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    card_paid_rial: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    address_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    delivery_location: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    delivery_note: Mapped[str | None] = mapped_column(Text)
    admin_note: Mapped[str | None] = mapped_column(Text)

    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    history: Mapped[list[OrderStatusHistory]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderStatusHistory.id"
    )

    __table_args__ = (
        CheckConstraint(
            "total_rial = subtotal_rial + delivery_fee_rial - discount_rial", name="total_math"
        ),
        CheckConstraint(
            f"status IN ({','.join(f"'{s}'" for s in ORDER_STATUSES)})", name="status_valid"
        ),
        CheckConstraint(
            f"payment_state IN ({','.join(f"'{s}'" for s in PAYMENT_STATES)})",
            name="payment_state_valid",
        ),
    )


class OrderItem(CreatedAtMixin, Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    title_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_price_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_rial: Mapped[int] = mapped_column(BigInteger, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("qty > 0", name="qty_positive"),
        CheckConstraint("line_total_rial = unit_price_rial * qty", name="line_math"),
    )


class OrderStatusHistory(CreatedAtMixin, Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(Text)

    order: Mapped[Order] = relationship(back_populates="history")

    __table_args__ = (
        CheckConstraint(
            f"source IN ({','.join(f"'{s}'" for s in TRANSITION_SOURCES)})", name="source_valid"
        ),
    )
