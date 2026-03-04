from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.library import LibraryEntryResponse, LibraryGameAdd
from api.services.library_service import LibraryService

router = APIRouter(prefix="/library", tags=["Library"])


@router.get("/", response_model=list[LibraryEntryResponse])
async def get_my_library(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[LibraryEntryResponse]:
    """Retorna todos os jogos da minha coleção com contagem de partidas."""
    service = LibraryService(session)
    return await service.get_my_library(current_user)


@router.post("/", response_model=LibraryEntryResponse, status_code=status.HTTP_201_CREATED)
async def add_game_to_library(
    body: LibraryGameAdd,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> LibraryEntryResponse:
    """Adiciona um jogo à minha coleção."""
    service = LibraryService(session)
    return await service.add_game(current_user, body.game_id)


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_game_from_library(
    game_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove um jogo da minha coleção."""
    service = LibraryService(session)
    await service.remove_game(current_user, game_id)


@router.get("/{user_id}", response_model=list[LibraryEntryResponse])
async def get_user_library(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[LibraryEntryResponse]:
    """Retorna a coleção de qualquer usuário."""
    service = LibraryService(session)
    return await service.get_user_library(user_id)
