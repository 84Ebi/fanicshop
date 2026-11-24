"""Signup and verification service tests against real PostgreSQL."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminAuditLog, User, UserEvent
from app.services.users import (
    InvalidProfile,
    InvalidTransition,
    PhoneTaken,
    approve_user,
    block_user,
    can_access_shop,
    confirm_age,
    count_pending,
    get_by_phone,
    get_by_telegram_id,
    get_or_create_user,
    list_pending,
    reject_user,
    search_users,
    submit_signup,
    unblock_user,
)


async def _new_user(session: AsyncSession, tg_id: int = 1001) -> User:
    user, created = await get_or_create_user(
        session, telegram_id=tg_id, username="tester", first_name="Test", last_name="User"
    )
    assert created
    await session.flush()
    return user


async def test_get_or_create_is_idempotent(db_session: AsyncSession) -> None:
    first, created = await get_or_create_user(db_session, telegram_id=42)
    second, created_again = await get_or_create_user(db_session, telegram_id=42)
    assert created and not created_again
    assert first.id == second.id
    assert await get_by_telegram_id(db_session, 42) is not None


async def test_full_signup_and_approval(db_session: AsyncSession) -> None:
    user = await _new_user(db_session)
    await confirm_age(db_session, user)
    await submit_signup(db_session, user, full_name="علی احمدی", phone="09121234567")

    assert user.status == "pending"
    assert user.phone == "9121234567"
    assert not can_access_shop(user)
    assert await count_pending(db_session) == 1
    assert await get_by_phone(db_session, "9121234567") is not None

    changed = await approve_user(db_session, user, actor_telegram_id=999)
    assert changed and user.status == "verified" and can_access_shop(user)
    assert not await approve_user(db_session, user, actor_telegram_id=999)  # idempotent

    events = (await db_session.scalars(select(UserEvent).where(UserEvent.user_id == user.id))).all()
    assert {e.event for e in events} >= {"signup", "age_confirm", "submitted", "approve"}
    audits = (await db_session.scalars(select(AdminAuditLog))).all()
    assert {a.action for a in audits} >= {"signup.submit", "user.approve"}


async def test_age_gate_and_bad_profile(db_session: AsyncSession) -> None:
    user = await _new_user(db_session)
    with pytest.raises(InvalidProfile):
        await submit_signup(db_session, user, full_name="علی احمدی", phone="09121234567")
    await confirm_age(db_session, user)
    with pytest.raises(InvalidProfile):
        await submit_signup(db_session, user, full_name="ع", phone="09121234567")
    with pytest.raises(InvalidProfile):
        await submit_signup(db_session, user, full_name="علی احمدی", phone="123")


async def test_phone_uniqueness_and_reject_reason(db_session: AsyncSession) -> None:
    a = await _new_user(db_session, 2001)
    b = await _new_user(db_session, 2002)
    for user in (a, b):
        await confirm_age(db_session, user)
    await submit_signup(db_session, a, full_name="علی احمدی", phone="09121234567")
    with pytest.raises(PhoneTaken):
        await submit_signup(db_session, b, full_name="محمد اسماعیلی", phone="9121234567")

    assert await reject_user(db_session, a, actor_telegram_id=999, reason="اطلاعات ناقص")
    assert a.status == "rejected" and a.rejection_reason == "اطلاعات ناقص"
    with pytest.raises(InvalidTransition):
        await approve_user(db_session, a, actor_telegram_id=999)


async def test_block_unblock_restores_status(db_session: AsyncSession) -> None:
    user = await _new_user(db_session, 3001)
    await confirm_age(db_session, user)
    await submit_signup(db_session, user, full_name="علی احمدی", phone="09121234567")
    await approve_user(db_session, user, actor_telegram_id=999)

    assert await block_user(db_session, user, actor_telegram_id=999, reason="تخلف")
    assert user.status == "blocked" and not can_access_shop(user)
    assert await unblock_user(db_session, user, actor_telegram_id=999)
    assert user.status == "verified" and can_access_shop(user)


async def test_listing_and_search(db_session: AsyncSession) -> None:
    user = await _new_user(db_session, 4001)
    await confirm_age(db_session, user)
    await submit_signup(db_session, user, full_name="علی احمدی", phone="09121234567")

    assert len(await list_pending(db_session)) == 1
    assert await search_users(db_session, "9121234567") == [user]
    assert await search_users(db_session, "4001") == [user]
    assert await search_users(db_session, "احمدی") == [user]
