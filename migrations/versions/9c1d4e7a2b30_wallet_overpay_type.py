"""Allow payment_overpay wallet transactions.

Revision ID: 9c1d4e7a2b30
Revises: e377b3f752b4
Create Date: 2026-11-24
"""

from __future__ import annotations

from alembic import op

revision = "9c1d4e7a2b30"
down_revision = "e377b3f752b4"
branch_labels = None
depends_on = None

_TYPES = (
    "topup",
    "order_payment",
    "refund",
    "admin_credit",
    "admin_debit",
    "adjustment",
    "payment_overpay",
)


def _constraint() -> str:
    values = ",".join(f"'{value}'" for value in _TYPES)
    return f"type IN ({values})"


def upgrade() -> None:
    op.drop_constraint("type_valid", "wallet_transactions", type_="check")
    op.create_check_constraint(
        "type_valid", "wallet_transactions", _constraint()
    )


def downgrade() -> None:
    op.drop_constraint("type_valid", "wallet_transactions", type_="check")
    values = ",".join(f"'{value}'" for value in _TYPES if value != "payment_overpay")
    op.create_check_constraint(
        "type_valid", "wallet_transactions", f"type IN ({values})"
    )
