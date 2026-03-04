from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories.friendship_repository import FriendshipRepository
from api.repositories.match_repository import MatchRepository
from api.repositories.user_repository import UserRepository
from api.schemas.ranking import GameStats, RankingEntry, UserStats


class RankingService:
    def __init__(self, session: AsyncSession) -> None:
        self.match_repo = MatchRepository(session)
        self.user_repo = UserRepository(session)
        self.friendship_repo = FriendshipRepository(session)

    async def _get_friend_ids(self, user_id: UUID) -> list[UUID]:
        friendships = await self.friendship_repo.get_friends(user_id)
        ids: list[UUID] = [user_id]
        for f in friendships:
            friend_id = f.addressee_id if f.requester_id == user_id else f.requester_id
            ids.append(friend_id)
        return ids

    async def get_global_ranking(
        self, current_user_id: UUID, limit: int = 50
    ) -> list[RankingEntry]:
        user_ids = await self._get_friend_ids(current_user_id)
        rows = await self.match_repo.get_global_ranking(limit=limit, user_ids=user_ids)
        return [
            RankingEntry(
                user_id=row["user_id"],
                username=row["username"],
                total_matches=row["total_matches"],
                total_wins=row["total_wins"],
                win_rate=round(row["total_wins"] / row["total_matches"] * 100, 2)
                if row["total_matches"] > 0
                else 0.0,
            )
            for row in rows
        ]

    async def get_ranking_by_game(
        self, game_id: UUID, current_user_id: UUID, limit: int = 50
    ) -> list[RankingEntry]:
        user_ids = await self._get_friend_ids(current_user_id)
        rows = await self.match_repo.get_ranking_by_game(
            game_id, limit=limit, user_ids=user_ids
        )
        return [
            RankingEntry(
                user_id=row["user_id"],
                username=row["username"],
                total_matches=row["total_matches"],
                total_wins=row["total_wins"],
                win_rate=round(row["total_wins"] / row["total_matches"] * 100, 2)
                if row["total_matches"] > 0
                else 0.0,
            )
            for row in rows
        ]

    async def get_user_stats(self, user_id: UUID) -> UserStats:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )

        game_rows = await self.match_repo.get_user_stats(user_id)

        total_matches = sum(r["total_matches"] for r in game_rows)
        total_wins = sum(r["total_wins"] for r in game_rows)

        return UserStats(
            user_id=user.id,
            username=user.username,
            total_matches=total_matches,
            total_wins=total_wins,
            win_rate=round(total_wins / total_matches * 100, 2)
            if total_matches > 0
            else 0.0,
            matches_by_game=[
                GameStats(
                    game_id=r["game_id"],
                    game_name=r["game_name"],
                    total_matches=r["total_matches"],
                    total_wins=r["total_wins"],
                    win_rate=round(
                        r["total_wins"] / r["total_matches"] * 100, 2
                    )
                    if r["total_matches"] > 0
                    else 0.0,
                )
                for r in game_rows
            ],
        )
