from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.match import Match
from api.models.match_player import MatchPlayer
from api.models.user_game_library import UserGameLibrary


class LibraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: UUID, game_id: UUID) -> UserGameLibrary:
        entry = UserGameLibrary(user_id=user_id, game_id=game_id)
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def remove(self, entry: UserGameLibrary) -> None:
        await self.session.delete(entry)
        await self.session.commit()

    async def get_entry(
        self, user_id: UUID, game_id: UUID
    ) -> UserGameLibrary | None:
        stmt = select(UserGameLibrary).where(
            UserGameLibrary.user_id == user_id,
            UserGameLibrary.game_id == game_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: UUID) -> list[UserGameLibrary]:
        stmt = (
            select(UserGameLibrary)
            .where(UserGameLibrary.user_id == user_id)
            .order_by(UserGameLibrary.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_matches_for_game(
        self, user_id: UUID, game_id: UUID
    ) -> int:
        """Conta quantas partidas o usuário jogou de um determinado jogo."""
        stmt = (
            select(func.count())
            .select_from(MatchPlayer)
            .join(Match, Match.id == MatchPlayer.match_id)
            .where(
                MatchPlayer.user_id == user_id,
                Match.game_id == game_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def get_owners_of_game(
        self, game_id: UUID, user_ids: list[UUID]
    ) -> list[UUID]:
        """Retorna quais usuários da lista possuem o jogo na biblioteca."""
        if not user_ids:
            return []
        stmt = select(UserGameLibrary.user_id).where(
            UserGameLibrary.game_id == game_id,
            UserGameLibrary.user_id.in_(user_ids),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
