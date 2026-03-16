from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from api.models.game import Game
from api.models.guest import Guest
from api.models.match import Match
from api.models.match_player import MatchPlayer
from api.models.user import User
from api.repositories.guest_repository import GuestRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_merge_guest_history_deduplicates_and_preserves_single_player(db_session):
    user = User(username="target", email="target@example.com", hashed_password="x")
    owner_a = User(username="owner_a", email="owner_a@example.com", hashed_password="x")
    owner_b = User(username="owner_b", email="owner_b@example.com", hashed_password="x")
    game = Game(name="Test Game", min_players=1, max_players=6)

    db_session.add_all([user, owner_a, owner_b, game])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(owner_a)
    await db_session.refresh(owner_b)
    await db_session.refresh(game)

    guest_a = Guest(owner_id=owner_a.id, name="Guest A", email="merge@example.com")
    guest_b = Guest(owner_id=owner_b.id, name="Guest B", email="merge@example.com")
    db_session.add_all([guest_a, guest_b])
    await db_session.commit()
    await db_session.refresh(guest_a)
    await db_session.refresh(guest_b)

    m1 = Match(game_id=game.id, created_by=owner_a.id, played_at=_utcnow())
    m2 = Match(game_id=game.id, created_by=owner_a.id, played_at=_utcnow())
    m3 = Match(game_id=game.id, created_by=owner_b.id, played_at=_utcnow())
    db_session.add_all([m1, m2, m3])
    await db_session.commit()
    await db_session.refresh(m1)
    await db_session.refresh(m2)
    await db_session.refresh(m3)

    # m1 has two guest rows for same future user (must deduplicate to one)
    # m2 already has user row (guest row should be deleted)
    # m3 has one guest row (should convert to user)
    players = [
        MatchPlayer(match_id=m1.id, guest_id=guest_a.id, position=1, score=10, is_winner=True),
        MatchPlayer(match_id=m1.id, guest_id=guest_b.id, position=2, score=8, is_winner=False),
        MatchPlayer(match_id=m2.id, guest_id=guest_a.id, position=2, score=6, is_winner=False),
        MatchPlayer(match_id=m2.id, user_id=user.id, position=1, score=12, is_winner=True),
        MatchPlayer(match_id=m3.id, guest_id=guest_b.id, position=1, score=15, is_winner=True),
    ]
    db_session.add_all(players)
    await db_session.commit()

    repo = GuestRepository(db_session)
    result = await repo.merge_guest_history_into_user_by_email("merge@example.com", user.id)

    assert result["matched_guests"] == 2
    assert result["updated_players"] == 2
    assert result["deleted_duplicates"] == 2

    rows = (
        await db_session.execute(
            select(MatchPlayer).where(MatchPlayer.match_id.in_([m1.id, m2.id, m3.id]))
        )
    ).scalars().all()

    by_match = {
        m1.id: [r for r in rows if r.match_id == m1.id],
        m2.id: [r for r in rows if r.match_id == m2.id],
        m3.id: [r for r in rows if r.match_id == m3.id],
    }

    assert len(by_match[m1.id]) == 1
    assert by_match[m1.id][0].user_id == user.id
    assert by_match[m1.id][0].guest_id is None

    assert len(by_match[m2.id]) == 1
    assert by_match[m2.id][0].user_id == user.id

    assert len(by_match[m3.id]) == 1
    assert by_match[m3.id][0].user_id == user.id
    assert by_match[m3.id][0].guest_id is None
