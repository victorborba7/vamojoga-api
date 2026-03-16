from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.game import Game
from api.models.user_game_favorite import UserGameFavorite


class FavoriteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: UUID, game_id: UUID) -> UserGameFavorite:
        entry = UserGameFavorite(user_id=user_id, game_id=game_id)
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def remove(self, entry: UserGameFavorite) -> None:
        await self.session.delete(entry)
        await self.session.commit()

    async def get_entry(self, user_id: UUID, game_id: UUID) -> UserGameFavorite | None:
        stmt = select(UserGameFavorite).where(
            UserGameFavorite.user_id == user_id,
            UserGameFavorite.game_id == game_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: UUID) -> list[UserGameFavorite]:
        stmt = (
            select(UserGameFavorite)
            .where(UserGameFavorite.user_id == user_id)
            .order_by(UserGameFavorite.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user_with_games(self, user_id: UUID) -> list[tuple[UserGameFavorite, Game]]:
        stmt = (
            select(UserGameFavorite, Game)
            .join(Game, Game.id == UserGameFavorite.game_id)
            .where(UserGameFavorite.user_id == user_id)
            .order_by(UserGameFavorite.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.tuples().all())

    async def get_game_ids(self, user_id: UUID) -> set[UUID]:
        stmt = select(UserGameFavorite.game_id).where(UserGameFavorite.user_id == user_id)
        result = await self.session.execute(stmt)
        return set(result.scalars().all())
