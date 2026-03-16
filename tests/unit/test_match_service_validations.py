from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from api.models.friendship import Friendship
from api.models.game import Game
from api.models.guest import Guest
from api.models.user import User
from api.schemas.match import MatchCreate, MatchPlayerCreate
from api.services.match_service import MatchService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_create_match_rejects_participant_without_user_or_guest(db_session):
    current = User(username="m_owner1", email="m_owner1@example.com", hashed_password="x")
    other = User(username="m_other1", email="m_other1@example.com", hashed_password="x")
    game = Game(name="Match Validations 1", min_players=2, max_players=6)
    db_session.add_all([current, other, game])
    await db_session.commit()
    await db_session.refresh(current)
    await db_session.refresh(other)
    await db_session.refresh(game)

    service = MatchService(db_session)
    data = MatchCreate(
        game_id=game.id,
        players=[
            MatchPlayerCreate(position=1, score=10, is_winner=True),
            MatchPlayerCreate(user_id=other.id, position=2, score=5, is_winner=False),
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_match(data, current)

    assert exc.value.status_code == 400
    assert "Cada participante" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_create_match_rejects_participant_with_both_user_and_guest(db_session):
    current = User(username="m_owner2", email="m_owner2@example.com", hashed_password="x")
    other = User(username="m_other2", email="m_other2@example.com", hashed_password="x")
    game = Game(name="Match Validations 2", min_players=2, max_players=6)
    db_session.add_all([current, other, game])
    await db_session.commit()
    await db_session.refresh(current)
    await db_session.refresh(other)
    await db_session.refresh(game)

    guest = Guest(owner_id=current.id, name="Guest A", email="ga@example.com")
    db_session.add(guest)
    await db_session.commit()
    await db_session.refresh(guest)

    service = MatchService(db_session)
    data = MatchCreate(
        game_id=game.id,
        players=[
            MatchPlayerCreate(user_id=other.id, guest_id=guest.id, position=1, score=10, is_winner=True),
            MatchPlayerCreate(user_id=current.id, position=2, score=6, is_winner=False),
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_match(data, current)

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_match_rejects_duplicate_participants(db_session):
    current = User(username="m_owner3", email="m_owner3@example.com", hashed_password="x")
    game = Game(name="Match Validations 3", min_players=2, max_players=6)
    db_session.add_all([current, game])
    await db_session.commit()
    await db_session.refresh(current)
    await db_session.refresh(game)

    service = MatchService(db_session)
    data = MatchCreate(
        game_id=game.id,
        players=[
            MatchPlayerCreate(user_id=current.id, position=1, score=10, is_winner=True),
            MatchPlayerCreate(user_id=current.id, position=2, score=8, is_winner=False),
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_match(data, current)

    assert exc.value.status_code == 400
    assert "duplicados" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_create_match_rejects_guest_not_owned_by_current_user(db_session):
    current = User(username="m_owner4", email="m_owner4@example.com", hashed_password="x")
    owner_other = User(username="m_owner4b", email="m_owner4b@example.com", hashed_password="x")
    game = Game(name="Match Validations 4", min_players=2, max_players=6)
    db_session.add_all([current, owner_other, game])
    await db_session.commit()
    await db_session.refresh(current)
    await db_session.refresh(owner_other)
    await db_session.refresh(game)

    guest = Guest(owner_id=owner_other.id, name="Guest B", email="gb@example.com")
    db_session.add(guest)
    await db_session.commit()
    await db_session.refresh(guest)

    service = MatchService(db_session)
    data = MatchCreate(
        game_id=game.id,
        players=[
            MatchPlayerCreate(user_id=current.id, position=1, score=11, is_winner=True),
            MatchPlayerCreate(guest_id=guest.id, position=2, score=4, is_winner=False),
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_match(data, current)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_match_rejects_collaborative_with_guest(db_session):
    current = User(username="m_owner5", email="m_owner5@example.com", hashed_password="x")
    other = User(username="m_other5", email="m_other5@example.com", hashed_password="x")
    game = Game(name="Match Validations 5", min_players=2, max_players=6)
    db_session.add_all([current, other, game])
    await db_session.commit()
    await db_session.refresh(current)
    await db_session.refresh(other)
    await db_session.refresh(game)

    guest = Guest(owner_id=current.id, name="Guest C", email="gc@example.com")
    db_session.add(guest)
    await db_session.commit()
    await db_session.refresh(guest)

    service = MatchService(db_session)
    data = MatchCreate(
        game_id=game.id,
        collaborative_scoring=True,
        players=[
            MatchPlayerCreate(user_id=other.id, position=1, score=0, is_winner=False),
            MatchPlayerCreate(guest_id=guest.id, position=1, score=0, is_winner=False),
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_match(data, current)

    assert exc.value.status_code == 400
    assert "nao permitem convidados" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_create_match_with_guest_returns_participant_names(db_session):
    current = User(username="m_owner6", email="m_owner6@example.com", hashed_password="x")
    other = User(username="m_other6", email="m_other6@example.com", hashed_password="x")
    game = Game(name="Match Validations 6", min_players=2, max_players=6)
    db_session.add_all([current, other, game])
    await db_session.commit()
    await db_session.refresh(current)
    await db_session.refresh(other)
    await db_session.refresh(game)

    guest = Guest(owner_id=current.id, name="Guest Named", email="gn@example.com")
    db_session.add(guest)
    await db_session.commit()
    await db_session.refresh(guest)

    service = MatchService(db_session)
    data = MatchCreate(
        game_id=game.id,
        players=[
            MatchPlayerCreate(user_id=other.id, position=1, score=20, is_winner=True),
            MatchPlayerCreate(guest_id=guest.id, position=2, score=7, is_winner=False),
        ],
    )

    response = await service.create_match(data, current)

    assert len(response.players) == 2
    names = {p.participant_name for p in response.players}
    assert "m_other6" in names
    assert "Guest Named" in names


@pytest.mark.asyncio
async def test_notify_friends_only_when_friend_is_participant(db_session):
    current = User(username="m_owner7", email="m_owner7@example.com", hashed_password="x")
    friend_in = User(username="m_friend_in", email="m_friend_in@example.com", hashed_password="x")
    friend_out = User(username="m_friend_out", email="m_friend_out@example.com", hashed_password="x")
    game = Game(name="Match Validations 7", min_players=2, max_players=6)
    db_session.add_all([current, friend_in, friend_out, game])
    await db_session.commit()
    await db_session.refresh(current)
    await db_session.refresh(friend_in)
    await db_session.refresh(friend_out)
    await db_session.refresh(game)

    db_session.add_all([
        Friendship(requester_id=current.id, addressee_id=friend_in.id, status="accepted"),
        Friendship(requester_id=current.id, addressee_id=friend_out.id, status="accepted"),
    ])
    await db_session.commit()

    service = MatchService(db_session)

    sent: list[tuple[str, str]] = []

    async def fake_send_to_user(user_id, title, body, url="/"):
        sent.append((str(user_id), title))

    service.push_service.send_to_user = fake_send_to_user  # type: ignore[method-assign]

    players_data = [
        SimpleNamespace(user_id=current.id),
        SimpleNamespace(user_id=friend_in.id),
    ]

    await service._award_achievements_and_notify(
        players_data=players_data,
        match_id=uuid4(),
        game_id=game.id,
        current_user=current,
        game=game,
        notify_friends_about_registration=True,
    )

    # Let scheduled tasks run.
    await __import__("asyncio").sleep(0.05)

    recipient_ids = {uid for uid, _ in sent}
    assert str(friend_in.id) in recipient_ids
    assert str(friend_out.id) not in recipient_ids
