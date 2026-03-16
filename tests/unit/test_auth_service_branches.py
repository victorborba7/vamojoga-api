from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from api.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_login_success_by_email(monkeypatch):
    user = SimpleNamespace(id=uuid4(), hashed_password="hash", is_active=True)

    service = AuthService(None)  # type: ignore[arg-type]
    service.repository = SimpleNamespace(
        get_by_email=AsyncMock(return_value=user),
        get_by_username=AsyncMock(),
    )

    monkeypatch.setattr("api.services.auth_service.verify_password", lambda plain, hashed: True)
    monkeypatch.setattr("api.services.auth_service.create_access_token", lambda user_id: "token-123")

    response = await service.login(SimpleNamespace(identifier="user@example.com", password="secret"))
    assert response.access_token == "token-123"
    service.repository.get_by_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_invalid_credentials_and_inactive_user(monkeypatch):
    service = AuthService(None)  # type: ignore[arg-type]
    service.repository = SimpleNamespace(
        get_by_email=AsyncMock(),
        get_by_username=AsyncMock(return_value=None),
    )

    monkeypatch.setattr("api.services.auth_service.verify_password", lambda plain, hashed: False)

    with pytest.raises(HTTPException) as invalid_exc:
        await service.login(SimpleNamespace(identifier="username", password="secret"))
    assert invalid_exc.value.status_code == 401

    inactive_user = SimpleNamespace(id=uuid4(), hashed_password="hash", is_active=False)
    service.repository.get_by_username = AsyncMock(return_value=inactive_user)
    monkeypatch.setattr("api.services.auth_service.verify_password", lambda plain, hashed: True)

    with pytest.raises(HTTPException) as inactive_exc:
        await service.login(SimpleNamespace(identifier="username", password="secret"))
    assert inactive_exc.value.status_code == 403


@pytest.mark.asyncio
async def test_forgot_password_silent_for_unknown_email_and_create_for_known(monkeypatch):
    session = SimpleNamespace(add=Mock(), commit=AsyncMock())
    service = AuthService(session)  # type: ignore[arg-type]

    service.repository = SimpleNamespace(
        get_by_email=AsyncMock(side_effect=[None, SimpleNamespace(id=uuid4(), email="known@example.com", username="known")])
    )

    # Unknown e-mail: should return silently.
    await service.forgot_password("unknown@example.com")
    assert session.commit.await_count == 0

    monkeypatch.setattr("api.services.auth_service.send_password_reset_email", lambda *_args, **_kwargs: None)
    await service.forgot_password("known@example.com")
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_link_guest_owners_as_friends_create_update_and_skip_self():
    new_user_id = uuid4()
    owner_create = uuid4()
    owner_update = uuid4()
    owner_keep = uuid4()

    pending = SimpleNamespace(status="pending")
    accepted = SimpleNamespace(status="accepted")

    friendship_repo = SimpleNamespace(
        get_between_users=AsyncMock(side_effect=[None, pending, accepted]),
        create=AsyncMock(),
        update_status=AsyncMock(),
    )

    service = AuthService(None)  # type: ignore[arg-type]
    service.friendship_repository = friendship_repo

    result = await service._link_guest_owners_as_friends(
        new_user_id=new_user_id,
        owner_ids=[new_user_id, owner_create, owner_update, owner_keep],
    )

    assert result == {"created": 1, "updated": 1}
    friendship_repo.create.assert_awaited_once()
    friendship_repo.update_status.assert_awaited_once_with(pending, "accepted")
