from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import select

from api.models.friendship import Friendship
from api.models.guest import Guest
from api.models.guest_invite_token import GuestInviteToken
from api.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_register_with_invalid_invite_token_returns_400(client):
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "inv_invalid",
            "email": "inv_invalid@example.com",
            "password": "12345678",
            "invite_token": "does-not-exist",
        },
    )
    assert res.status_code == 400
    assert "Convite" in res.json()["detail"]


@pytest.mark.asyncio
async def test_register_with_invite_token_email_mismatch_returns_400(client, db_session):
    owner = User(username="inv_owner1", email="inv_owner1@example.com", hashed_password="x")
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    guest = Guest(owner_id=owner.id, name="Guest Invite", email="right@example.com")
    db_session.add(guest)
    await db_session.commit()
    await db_session.refresh(guest)

    token = GuestInviteToken(
        guest_id=guest.id,
        email="right@example.com",
        token="tok-mismatch",
        expires_at=_utcnow() + timedelta(days=1),
        used=False,
    )
    db_session.add(token)
    await db_session.commit()

    res = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "inv_mismatch",
            "email": "other@example.com",
            "password": "12345678",
            "invite_token": "tok-mismatch",
        },
    )

    assert res.status_code == 400
    assert "outro e-mail" in res.json()["detail"]


@pytest.mark.asyncio
async def test_register_with_valid_invite_consumes_token_and_creates_friendship(client, db_session):
    owner = User(username="inv_owner2", email="inv_owner2@example.com", hashed_password="x")
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)
    owner_id = owner.id

    guest_email = "valid-invite@example.com"
    guest = Guest(owner_id=owner.id, name="Guest Invite 2", email=guest_email)
    db_session.add(guest)
    await db_session.commit()
    await db_session.refresh(guest)

    token = GuestInviteToken(
        guest_id=guest.id,
        email=guest_email,
        token="tok-valid",
        expires_at=_utcnow() + timedelta(days=1),
        used=False,
    )
    db_session.add(token)
    await db_session.commit()

    res = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "inv_valid",
            "email": guest_email,
            "password": "12345678",
            "invite_token": "tok-valid",
        },
    )

    assert res.status_code == 201
    created_user_id = res.json()["id"]
    created_user_uuid = UUID(created_user_id)

    db_session.expire_all()
    refreshed_token = (
        await db_session.execute(
            select(GuestInviteToken)
            .where(GuestInviteToken.token == "tok-valid")
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert refreshed_token.used is True

    friendship = (
        await db_session.execute(
            select(Friendship).where(
                Friendship.requester_id == owner_id,
                Friendship.addressee_id == created_user_uuid,
            )
        )
    ).scalar_one_or_none()

    # SQLite may keep UUID as str; normalize comparison by presence and status.
    assert friendship is not None
    assert friendship.status == "accepted"
