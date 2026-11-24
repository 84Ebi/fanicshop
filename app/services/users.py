"""User identity, signup and admin verification transitions.

Every state change appends a ``user_events`` row; admin actions also write to
``admin_audit_log``. Handlers commit the session after calling these services.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserEvent
from app.services.audit import audit
from app.utils.names import normalize_name
from app.utils.phone import normalize_phone

SUBMITTABLE_STATUSES = ("draft", "rejected")


class UserError(Exception):
    """Base for user-flow errors (safe to show a generic message)."""


class PhoneTaken(UserError):
    pass


class InvalidTransition(UserError):
    pass


class InvalidProfile(UserError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def display_name(user: User) -> str:
    return user.full_name or "دوست عزیز"


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_by_phone(session: AsyncSession, phone: str) -> User | None:
    return await session.scalar(select(User).where(User.phone == phone))


async def get_or_create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> tuple[User, bool]:
    """Return (user, created). Updates the Telegram profile snapshot."""
    user = await get_by_telegram_id(session, telegram_id)
    created = user is None
    if user is None:
        fallback = " ".join(x for x in (first_name, last_name) if x).strip()
        user = User(
            telegram_id=telegram_id,
            username=username,
            tg_first_name=first_name,
            tg_last_name=last_name,
            full_name=(fallback[:60] or "کاربر مهمان"),
            status="draft",
        )
        session.add(user)
        await session.flush()
        await _event(session, user, "signup", None, "draft")
    else:
        user.username = username
        user.tg_first_name = first_name
        user.tg_last_name = last_name
    user.last_seen_at = _now()
    return user, created


async def _event(
    session: AsyncSession,
    user: User,
    event: str,
    from_status: str | None,
    to_status: str | None,
    *,
    actor_telegram_id: int | None = None,
    reason: str | None = None,
) -> None:
    session.add(
        UserEvent(
            user_id=user.id,
            event=event,
            from_status=from_status,
            to_status=to_status,
            actor_telegram_id=actor_telegram_id,
            reason=reason,
        )
    )


async def confirm_age(session: AsyncSession, user: User) -> None:
    if user.age_confirmed_at is None:
        user.age_confirmed_at = _now()
        await _event(session, user, "age_confirm", user.status, user.status)
    await session.flush()


async def submit_signup(
    session: AsyncSession,
    user: User,
    *,
    full_name: str,
    phone: str,
) -> User:
    if user.status not in SUBMITTABLE_STATUSES:
        raise InvalidTransition(f"cannot submit from {user.status}")
    if user.age_confirmed_at is None:
        raise InvalidProfile("age not confirmed")

    name = normalize_name(full_name)
    normalized_phone = normalize_phone(phone)
    if name is None or normalized_phone is None:
        raise InvalidProfile("invalid name or phone")

    other = await get_by_phone(session, normalized_phone)
    if other is not None and other.id != user.id:
        raise PhoneTaken(normalized_phone)

    before = {"status": user.status, "full_name": user.full_name, "phone": user.phone}
    user.full_name = name
    user.phone = normalized_phone
    user.status = "pending"
    user.rejection_reason = None
    try:
        await session.flush()
    except IntegrityError as exc:  # concurrent signup with the same phone
        raise PhoneTaken(normalized_phone) from exc

    await _event(session, user, "submitted", before["status"], "pending")
    await audit(
        session,
        actor_telegram_id=user.telegram_id,
        action="signup.submit",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after={"status": "pending", "full_name": name, "phone": normalized_phone},
    )
    await session.flush()
    return user


async def approve_user(session: AsyncSession, user: User, *, actor_telegram_id: int) -> bool:
    """pending → verified. Returns False when already verified (idempotent)."""
    if user.status == "verified":
        return False
    if user.status != "pending":
        raise InvalidTransition(f"cannot approve from {user.status}")
    user.status = "verified"
    user.rejection_reason = None
    await _event(
        session,
        user,
        "approve",
        "pending",
        "verified",
        actor_telegram_id=actor_telegram_id,
    )
    await audit(
        session,
        actor_telegram_id=actor_telegram_id,
        action="user.approve",
        entity_type="user",
        entity_id=user.id,
        before={"status": "pending"},
        after={"status": "verified"},
    )
    await session.flush()
    return True


async def reject_user(
    session: AsyncSession, user: User, *, actor_telegram_id: int, reason: str
) -> bool:
    if user.status == "rejected":
        return False
    if user.status != "pending":
        raise InvalidTransition(f"cannot reject from {user.status}")
    user.status = "rejected"
    user.rejection_reason = reason
    await _event(
        session,
        user,
        "reject",
        "pending",
        "rejected",
        actor_telegram_id=actor_telegram_id,
        reason=reason,
    )
    await audit(
        session,
        actor_telegram_id=actor_telegram_id,
        action="user.reject",
        entity_type="user",
        entity_id=user.id,
        before={"status": "pending"},
        after={"status": "rejected", "reason": reason},
    )
    await session.flush()
    return True


async def block_user(
    session: AsyncSession, user: User, *, actor_telegram_id: int, reason: str
) -> bool:
    if user.status == "blocked":
        return False
    previous = user.status
    user.status = "blocked"
    user.block_reason = reason
    await _event(
        session,
        user,
        "block",
        previous,
        "blocked",
        actor_telegram_id=actor_telegram_id,
        reason=reason,
    )
    await audit(
        session,
        actor_telegram_id=actor_telegram_id,
        action="user.block",
        entity_type="user",
        entity_id=user.id,
        before={"status": previous},
        after={"status": "blocked", "reason": reason},
    )
    await session.flush()
    return True


async def _status_before_block(session: AsyncSession, user: User) -> str:
    row = await session.scalar(
        select(UserEvent.from_status)
        .where(UserEvent.user_id == user.id, UserEvent.event == "block")
        .order_by(UserEvent.id.desc())
        .limit(1)
    )
    return row if row in ("pending", "verified") else "pending"


async def unblock_user(session: AsyncSession, user: User, *, actor_telegram_id: int) -> bool:
    if user.status != "blocked":
        return False
    restored = await _status_before_block(session, user)
    user.status = restored
    user.block_reason = None
    await _event(session, user, "unblock", "blocked", restored, actor_telegram_id=actor_telegram_id)
    await audit(
        session,
        actor_telegram_id=actor_telegram_id,
        action="user.unblock",
        entity_type="user",
        entity_id=user.id,
        before={"status": "blocked"},
        after={"status": restored},
    )
    await session.flush()
    return True


def can_access_shop(user: User | None) -> bool:
    return user is not None and user.status == "verified"


async def count_pending(session: AsyncSession) -> int:
    return int(
        await session.scalar(select(func.count()).select_from(User).where(User.status == "pending")) or 0
    )


async def list_pending(session: AsyncSession, *, limit: int = 8, offset: int = 0) -> list[User]:
    rows = await session.scalars(
        select(User)
        .where(User.status == "pending")
        .order_by(User.created_at.asc(), User.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows)


async def search_users(session: AsyncSession, query: str, *, limit: int = 10) -> list[User]:
    q = query.strip()
    if not q:
        return []
    clauses = []
    normalized = normalize_phone(q)
    if normalized:
        clauses.append(User.phone == normalized)
    if q.isdigit():
        clauses.append(User.telegram_id == int(q))
        clauses.append(User.id == int(q))
    clauses.append(User.full_name.ilike(f"%{q}%"))
    rows = await session.scalars(
        select(User).where(or_(*clauses)).order_by(User.id.desc()).limit(limit)
    )
    return list(rows)
