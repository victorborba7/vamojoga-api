from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.game import Game
from api.models.user import User
from api.repositories.favorite_repository import FavoriteRepository
from api.repositories.game_repository import GameRepository
from api.schemas.game import GameResponse
from api.schemas.library import LibraryEntryResponse


def _game_to_response(game: Game) -> GameResponse:
    return GameResponse.model_validate(game, from_attributes=True)


class FavoriteService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = FavoriteRepository(session)
        self.game_repo = GameRepository(session)

    async def add(self, user: User, game_id: UUID) -> LibraryEntryResponse:
        game = await self.game_repo.get_by_id(game_id)
        if not game:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jogo não encontrado")

        existing = await self.repo.get_entry(user.id, game_id)
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Jogo já está nos favoritos")

        entry = await self.repo.add(user.id, game_id)
        return LibraryEntryResponse(
            id=entry.id,
            game=_game_to_response(game),
            match_count=0,
            added_at=entry.created_at,
        )

    async def remove(self, user: User, game_id: UUID) -> None:
        entry = await self.repo.get_entry(user.id, game_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jogo não está nos favoritos")
        await self.repo.remove(entry)

    async def get_my_favorites(self, user: User) -> list[LibraryEntryResponse]:
        rows = await self.repo.get_by_user_with_games(user.id)
        return [
            LibraryEntryResponse(
                id=entry.id,
                game=_game_to_response(game),
                match_count=0,
                added_at=entry.created_at,
            )
            for entry, game in rows
        ]
