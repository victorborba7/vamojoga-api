from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.game import Game
from api.repositories.game_repository import GameRepository
from api.schemas.game import GameCreate, GameResponse, GameUpdate


class GameService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = GameRepository(session)

    async def create_game(self, data: GameCreate) -> GameResponse:
        existing = await self.repository.get_by_name(data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Jogo com esse nome já existe",
            )

        if data.min_players > data.max_players:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_players não pode ser maior que max_players",
            )

        game = Game(**data.model_dump())
        created_game = await self.repository.create(game)
        return GameResponse.model_validate(created_game)

    async def get_game(self, game_id: UUID) -> GameResponse:
        game = await self.repository.get_by_id(game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jogo não encontrado",
            )
        return GameResponse.model_validate(game)

    async def list_games(self, skip: int = 0, limit: int = 100) -> list[GameResponse]:
        games = await self.repository.list_all(skip=skip, limit=limit)
        return [GameResponse.model_validate(g) for g in games]

    async def search_games(self, query: str, limit: int = 10) -> list[GameResponse]:
        games = await self.repository.search_by_name(query, limit=limit)
        return [GameResponse.model_validate(g) for g in games]

    async def update_game(self, game_id: UUID, data: GameUpdate) -> GameResponse:
        game = await self.repository.get_by_id(game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jogo não encontrado",
            )

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(game, key, value)

        min_p = update_data.get("min_players", game.min_players)
        max_p = update_data.get("max_players", game.max_players)
        if min_p > max_p:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_players não pode ser maior que max_players",
            )

        updated_game = await self.repository.update(game)
        return GameResponse.model_validate(updated_game)
