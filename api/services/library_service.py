from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.game import Game
from api.models.user import User
from api.repositories.game_repository import GameRepository
from api.repositories.library_repository import LibraryRepository
from api.schemas.game import GameResponse
from api.schemas.library import LibraryEntryResponse


def _game_to_response(game: Game) -> GameResponse:
    return GameResponse.model_validate(game, from_attributes=True)


class LibraryService:
    def __init__(self, session: AsyncSession) -> None:
        self.library_repo = LibraryRepository(session)
        self.game_repo = GameRepository(session)

    async def add_game(self, user: User, game_id: UUID) -> LibraryEntryResponse:
        game = await self.game_repo.get_by_id(game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jogo não encontrado",
            )

        existing = await self.library_repo.get_entry(user.id, game_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Jogo já está na sua coleção",
            )

        entry = await self.library_repo.add(user.id, game_id)
        match_count = await self.library_repo.count_matches_for_game(user.id, game_id)

        return LibraryEntryResponse(
            id=entry.id,
            game=_game_to_response(game),
            match_count=match_count,
            added_at=entry.created_at,
        )

    async def remove_game(self, user: User, game_id: UUID) -> None:
        entry = await self.library_repo.get_entry(user.id, game_id)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jogo não está na sua coleção",
            )
        await self.library_repo.remove(entry)

    async def _build_library(
        self, user_id: UUID
    ) -> list[LibraryEntryResponse]:
        rows = await self.library_repo.get_by_user_with_games(user_id)
        if not rows:
            return []

        game_ids = [game.id for _, game in rows]
        match_counts = await self.library_repo.batch_count_matches(
            user_id, game_ids
        )

        return [
            LibraryEntryResponse(
                id=entry.id,
                game=_game_to_response(game),
                match_count=match_counts.get(game.id, 0),
                added_at=entry.created_at,
            )
            for entry, game in rows
        ]

    async def get_my_library(self, user: User) -> list[LibraryEntryResponse]:
        return await self._build_library(user.id)

    async def get_user_library(self, owner_id: UUID) -> list[LibraryEntryResponse]:
        """Retorna a biblioteca pública de qualquer usuário."""
        return await self._build_library(owner_id)
