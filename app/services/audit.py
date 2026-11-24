"""Privileged-action audit trail."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminAuditLog


async def audit(
    session: AsyncSession,
    *,
    actor_telegram_id: int,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    session.add(
        AdminAuditLog(
            actor_telegram_id=actor_telegram_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )
