from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.library import LibraryEntryResponse, LibraryGameAdd
from api.services.favorite_service import FavoriteService

router = APIRouter(prefix="/favorites", tags=["Favorites"])


@router.get("/", response_model=list[LibraryEntryResponse])
async def get_my_favorites(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[LibraryEntryResponse]:
    service = FavoriteService(session)
    return await service.get_my_favorites(current_user)


@router.post("/", response_model=LibraryEntryResponse, status_code=status.HTTP_201_CREATED)
async def add_to_favorites(
    body: LibraryGameAdd,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> LibraryEntryResponse:
    service = FavoriteService(session)
    return await service.add(current_user, body.game_id)


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_favorites(
    game_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    service = FavoriteService(session)
    await service.remove(current_user, game_id)
