"""Support conversations (customer <-> admin) and broadcast log helpers."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Broadcast, SupportMessage, SupportThread


async def get_or_create_thread(session: AsyncSession, user_id: int) -> SupportThread:
    """Return the (single) support thread for a user, creating it if needed."""
    thread = await session.scalar(
        select(SupportThread).where(SupportThread.user_id == user_id)
    )
    if thread is None:
        thread = SupportThread(user_id=user_id)
        session.add(thread)
        await session.flush()
    return thread


async def append_support_message(
    session: AsyncSession,
    *,
    thread_id: int,
    direction: str,
    text: str | None = None,
    telegram_message_id: int | None = None,
) -> SupportMessage:
    message = SupportMessage(
        thread_id=thread_id,
        direction=direction,
        text=text,
        telegram_message_id=telegram_message_id,
    )
    session.add(message)
    await session.flush()
    return message


async def list_threads(
    session: AsyncSession,
    *,
    only_open: bool | None = None,
    limit: int = 8,
    offset: int = 0,
) -> list[SupportThread]:
    query = select(SupportThread).order_by(SupportThread.id.desc())
    if only_open is True:
        query = query.where(SupportThread.is_open.is_(True))
    elif only_open is False:
        query = query.where(SupportThread.is_open.is_(False))
    return list((await session.scalars(query.limit(limit).offset(offset))).all())


async def count_threads(
    session: AsyncSession, *, only_open: bool | None = None
) -> int:
    query = select(func.count()).select_from(SupportThread)
    if only_open is True:
        query = query.where(SupportThread.is_open.is_(True))
    elif only_open is False:
        query = query.where(SupportThread.is_open.is_(False))
    return int(await session.scalar(query) or 0)


async def get_thread(session: AsyncSession, thread_id: int) -> SupportThread | None:
    return await session.get(SupportThread, thread_id)


async def list_broadcasts(
    session: AsyncSession, *, limit: int = 8, offset: int = 0
) -> list[Broadcast]:
    return list(
        (
            await session.scalars(
                select(Broadcast)
                .order_by(Broadcast.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )


async def count_broadcasts(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(Broadcast)) or 0)
