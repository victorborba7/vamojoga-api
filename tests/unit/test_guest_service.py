from datetime import timedelta
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from api.models.guest import Guest
from api.models.guest_invite_token import GuestInviteToken
from api.models.user import User
from api.schemas.guest import GuestCreate, GuestUpdate
from api.services.guest_service import GuestService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_create_guest_with_email_creates_invite_token(db_session, monkeypatch):
    owner = User(username="g_owner1", email="g_owner1@example.com", hashed_password="x")
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    monkeypatch.setattr("api.services.guest_service.send_guest_invite_email", lambda *args, **kwargs: None)

    service = GuestService(db_session)
    response = await service.create_guest(
        GuestCreate(name="Guest Test", email="guest_token@example.com"),
        owner,
    )

    assert response.email == "guest_token@example.com"

    tokens = (
        await db_session.execute(
            select(GuestInviteToken).where(GuestInviteToken.guest_id == response.id)
        )
    ).scalars().all()
    assert len(tokens) == 1


@pytest.mark.asyncio
async def test_validate_invite_expired_returns_400(db_session):
    owner = User(username="g_owner2", email="g_owner2@example.com", hashed_password="x")
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    guest = Guest(owner_id=owner.id, name="Guest Expired", email="expired@example.com")
    db_session.add(guest)
    await db_session.commit()
    await db_session.refresh(guest)

    token = GuestInviteToken(
        guest_id=guest.id,
        email="expired@example.com",
        token="expired-token",
        expires_at=_utcnow() - timedelta(minutes=1),
        used=False,
    )
    db_session.add(token)
    await db_session.commit()

    service = GuestService(db_session)
    with pytest.raises(HTTPException) as exc:
        await service.validate_invite("expired-token")

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_update_guest_from_another_owner_returns_404(db_session):
    owner_a = User(username="g_owner3", email="g_owner3@example.com", hashed_password="x")
    owner_b = User(username="g_owner4", email="g_owner4@example.com", hashed_password="x")
    db_session.add_all([owner_a, owner_b])
    await db_session.commit()
    await db_session.refresh(owner_a)
    await db_session.refresh(owner_b)

    guest = Guest(owner_id=owner_a.id, name="Guest Locked", email="locked@example.com")
    db_session.add(guest)
    await db_session.commit()
    await db_session.refresh(guest)

    service = GuestService(db_session)
    with pytest.raises(HTTPException) as exc:
        await service.update_guest(
            guest_id=guest.id,
            data=GuestUpdate(name="Try Update"),
            current_user=owner_b,
        )

    assert exc.value.status_code == 404
