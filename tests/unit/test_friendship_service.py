from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from api.services.friendship_service import FriendshipService


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_send_request_validation_errors():
    service = FriendshipService(None)  # type: ignore[arg-type]
    service.user_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    service.friendship_repo = SimpleNamespace(get_between_users=AsyncMock())

    requester = SimpleNamespace(id=uuid4(), username="alice")

    with pytest.raises(HTTPException) as same_user_exc:
        await service.send_request(requester, requester.id)
    assert same_user_exc.value.status_code == 400

    with pytest.raises(HTTPException) as not_found_exc:
        await service.send_request(requester, uuid4())
    assert not_found_exc.value.status_code == 404


@pytest.mark.asyncio
async def test_send_request_pending_reverse_auto_accept(monkeypatch):
    requester_id = uuid4()
    addressee_id = uuid4()

    requester = SimpleNamespace(id=requester_id, username="alice")
    addressee = SimpleNamespace(id=addressee_id, username="bob")
    existing = SimpleNamespace(
        id=uuid4(),
        requester_id=addressee_id,
        addressee_id=requester_id,
        status="pending",
        created_at=_now(),
    )
    accepted_response = SimpleNamespace(status="accepted")

    service = FriendshipService(None)  # type: ignore[arg-type]
    service.user_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=addressee))
    service.friendship_repo = SimpleNamespace(get_between_users=AsyncMock(return_value=existing))
    service._accept = AsyncMock(return_value=accepted_response)

    response = await service.send_request(requester, addressee_id)
    assert response.status == "accepted"
    service._accept.assert_awaited_once()

    pending_same_direction = SimpleNamespace(
        id=uuid4(),
        requester_id=requester_id,
        addressee_id=addressee_id,
        status="pending",
        created_at=_now(),
    )
    service.friendship_repo.get_between_users = AsyncMock(return_value=pending_same_direction)
    with pytest.raises(HTTPException) as duplicate_exc:
        await service.send_request(requester, addressee_id)
    assert duplicate_exc.value.status_code == 400


@pytest.mark.asyncio
async def test_send_request_rejected_recreate_and_remove_friend(monkeypatch):
    requester_id = uuid4()
    addressee_id = uuid4()
    friendship_id = uuid4()

    requester = SimpleNamespace(id=requester_id, username="alice")
    addressee = SimpleNamespace(id=addressee_id, username="bob")
    rejected = SimpleNamespace(
        id=friendship_id,
        requester_id=requester_id,
        addressee_id=addressee_id,
        status="rejected",
        created_at=_now(),
    )
    created = SimpleNamespace(
        id=uuid4(),
        requester_id=requester_id,
        addressee_id=addressee_id,
        status="pending",
        created_at=_now(),
    )

    repo = SimpleNamespace(
        get_between_users=AsyncMock(return_value=rejected),
        delete=AsyncMock(),
        create=AsyncMock(return_value=created),
        get_by_id=AsyncMock(return_value=created),
    )

    service = FriendshipService(None)  # type: ignore[arg-type]
    service.friendship_repo = repo
    service.user_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=addressee))
    service.push_service = SimpleNamespace(send_to_user=AsyncMock())

    # Avoid background task noise in unit test.
    monkeypatch.setattr(
        "api.services.friendship_service.asyncio.create_task",
        lambda coro: coro.close() or None,
    )

    response = await service.send_request(requester, addressee_id)
    assert response.status == "pending"
    repo.delete.assert_awaited_once()
    repo.create.assert_awaited_once()

    with pytest.raises(HTTPException) as forbidden_remove:
        await service.remove_friend(created.id, SimpleNamespace(id=uuid4()))
    assert forbidden_remove.value.status_code == 403

    await service.remove_friend(created.id, requester)
    assert repo.delete.await_count == 2


@pytest.mark.asyncio
async def test_accept_and_reject_request_branches():
    requester_id = uuid4()
    addressee_id = uuid4()
    friendship_id = uuid4()

    pending = SimpleNamespace(
        id=friendship_id,
        requester_id=requester_id,
        addressee_id=addressee_id,
        status="pending",
        created_at=_now(),
    )
    accepted = SimpleNamespace(
        id=friendship_id,
        requester_id=requester_id,
        addressee_id=addressee_id,
        status="accepted",
        created_at=_now(),
    )
    rejected = SimpleNamespace(
        id=friendship_id,
        requester_id=requester_id,
        addressee_id=addressee_id,
        status="rejected",
        created_at=_now(),
    )

    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=pending),
        update_status=AsyncMock(side_effect=[accepted, rejected]),
    )
    user_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=SimpleNamespace(id=requester_id, username="alice")))

    service = FriendshipService(None)  # type: ignore[arg-type]
    service.friendship_repo = repo
    service.user_repo = user_repo

    current_user = SimpleNamespace(id=addressee_id, username="bob")

    accept_response = await service.accept_request(friendship_id, current_user)
    assert accept_response.status == "accepted"

    # For reject, make get_by_id return pending again.
    repo.get_by_id = AsyncMock(return_value=pending)
    reject_response = await service.reject_request(friendship_id, current_user)
    assert reject_response.status == "rejected"


@pytest.mark.asyncio
async def test_get_friends_and_pending_lists():
    user_id = uuid4()
    friend_id = uuid4()
    sent_id = uuid4()
    received_id = uuid4()

    accepted_friendship = SimpleNamespace(
        id=uuid4(),
        requester_id=user_id,
        addressee_id=friend_id,
        updated_at=_now(),
    )
    pending_received = SimpleNamespace(
        id=uuid4(),
        requester_id=received_id,
        addressee_id=user_id,
        status="pending",
        created_at=_now(),
    )
    pending_sent = SimpleNamespace(
        id=uuid4(),
        requester_id=user_id,
        addressee_id=sent_id,
        status="pending",
        created_at=_now(),
    )

    service = FriendshipService(None)  # type: ignore[arg-type]
    service.friendship_repo = SimpleNamespace(
        get_friends=AsyncMock(return_value=[accepted_friendship]),
        get_pending_received=AsyncMock(return_value=[pending_received]),
        get_pending_sent=AsyncMock(return_value=[pending_sent]),
    )
    service.user_repo = SimpleNamespace(
        get_by_ids=AsyncMock(
            side_effect=[
                [SimpleNamespace(id=friend_id, username="friend", full_name="Friend Name")],
                [SimpleNamespace(id=received_id, username="received", full_name=None)],
                [SimpleNamespace(id=sent_id, username="sent", full_name=None)],
            ]
        )
    )

    friends = await service.get_friends(user_id)
    assert len(friends) == 1
    assert friends[0].username == "friend"

    pending_received_list = await service.get_pending_received(user_id)
    assert len(pending_received_list) == 1
    assert pending_received_list[0].requester_username == "received"

    pending_sent_list = await service.get_pending_sent(user_id)
    assert len(pending_sent_list) == 1
    assert pending_sent_list[0].addressee_username == "sent"
