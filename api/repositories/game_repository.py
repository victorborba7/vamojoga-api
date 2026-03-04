from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.game import Game



class GameRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, game: Game) -> Game:
        self.session.add(game)
        await self.session.commit()
        await self.session.refresh(game)
        return game

    async def get_by_id(self, game_id: UUID) -> Game | None:
        statement = select(Game).where(Game.id == game_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Game | None:
        statement = select(Game).where(Game.name == name)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Game]:
        statement = select(Game).where(Game.is_active == True).offset(skip).limit(limit)  # noqa: E712
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def search_by_name(self, query: str, limit: int = 10) -> list[Game]:
        statement = (
            select(Game)
            .where(Game.is_active == True, Game.name.ilike(f"%{query}%"))  # noqa: E712
            .order_by(Game.name)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update(self, game: Game) -> Game:
        self.session.add(game)
        await self.session.commit()
        await self.session.refresh(game)
        return game
