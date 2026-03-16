from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from api.models.friendship import Friendship
from api.models.game import Game
from api.models.guest import Guest
from api.models.match import Match
from api.models.match_player import MatchPlayer
from api.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_register_merges_guest_history_and_links_friendships(client, db_session):
    owner_a = User(username="owner_a_i", email="owner_a_i@example.com", hashed_password="x")
    owner_b = User(username="owner_b_i", email="owner_b_i@example.com", hashed_password="x")
    game = Game(name="Integration Game", min_players=1, max_players=6)
    db_session.add_all([owner_a, owner_b, game])
    await db_session.commit()
    await db_session.refresh(owner_a)
    await db_session.refresh(owner_b)
    await db_session.refresh(game)

    guest_email = "guest.merge@example.com"
    guest_a = Guest(owner_id=owner_a.id, name="Convidado A", email=guest_email)
    guest_b = Guest(owner_id=owner_b.id, name="Convidado B", email=guest_email)
    db_session.add_all([guest_a, guest_b])
    await db_session.commit()
    await db_session.refresh(guest_a)
    await db_session.refresh(guest_b)

    m1 = Match(game_id=game.id, created_by=owner_a.id, played_at=_utcnow())
    m2 = Match(game_id=game.id, created_by=owner_b.id, played_at=_utcnow())
    db_session.add_all([m1, m2])
    await db_session.commit()
    await db_session.refresh(m1)
    await db_session.refresh(m2)

    db_session.add_all([
        MatchPlayer(match_id=m1.id, guest_id=guest_a.id, position=1, score=11, is_winner=True),
        MatchPlayer(match_id=m2.id, guest_id=guest_b.id, position=2, score=7, is_winner=False),
    ])
    await db_session.commit()

    res = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "merged_user",
            "email": guest_email,
            "password": "12345678",
            "full_name": "Merged User",
        },
    )

    assert res.status_code == 201
    payload = res.json()
    created_user_id = payload["id"]

    players = (
        await db_session.execute(
            select(MatchPlayer).where(MatchPlayer.match_id.in_([m1.id, m2.id]))
        )
    ).scalars().all()

    assert len(players) == 2
    assert all(str(p.user_id) == created_user_id for p in players)
    assert all(p.guest_id is None for p in players)

    friendships = (
        await db_session.execute(
            select(Friendship).where(
                (Friendship.requester_id == owner_a.id) | (Friendship.requester_id == owner_b.id)
            )
        )
    ).scalars().all()

    owner_friend_ids = {str(f.requester_id) for f in friendships if str(f.addressee_id) == created_user_id and f.status == "accepted"}
    assert str(owner_a.id) in owner_friend_ids
    assert str(owner_b.id) in owner_friend_ids
