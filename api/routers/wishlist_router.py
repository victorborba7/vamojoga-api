from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.library import WishlistEntryResponse, WishlistGameAdd, WishlistVisibilityUpdate
from api.services.wishlist_service import WishlistService

router = APIRouter(prefix="/wishlist", tags=["Wishlist"])


@router.get("/", response_model=list[WishlistEntryResponse])
async def get_my_wishlist(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[WishlistEntryResponse]:
    """Retorna minha wishlist com indicador de amigos que possuem cada jogo."""
    service = WishlistService(session)
    return await service.get_my_wishlist(current_user)


@router.post("/", response_model=WishlistEntryResponse, status_code=status.HTTP_201_CREATED)
async def add_game_to_wishlist(
    body: WishlistGameAdd,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> WishlistEntryResponse:
    """Adiciona um jogo à wishlist."""
    service = WishlistService(session)
    return await service.add_game(current_user, body.game_id, body.is_public)


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_game_from_wishlist(
    game_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove um jogo da wishlist."""
    service = WishlistService(session)
    await service.remove_game(current_user, game_id)


@router.patch("/{game_id}/visibility", response_model=WishlistEntryResponse)
async def update_wishlist_visibility(
    game_id: UUID,
    body: WishlistVisibilityUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> WishlistEntryResponse:
    """Altera a visibilidade (pública/privada) de um jogo na wishlist."""
    service = WishlistService(session)
    return await service.update_visibility(current_user, game_id, body)


@router.get("/{user_id}", response_model=list[WishlistEntryResponse])
async def get_user_wishlist(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[WishlistEntryResponse]:
    """
    Retorna a wishlist de outro usuário.
    Somente itens públicos são visíveis (exceto para o próprio dono).
    """
    service = WishlistService(session)
    return await service.get_user_wishlist(current_user, user_id)
