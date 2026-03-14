from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.collection import (
    CollectionCreate,
    CollectionDetailResponse,
    CollectionGameResponse,
    CollectionResponse,
    CollectionUpdate,
    MemberResponse,
)
from api.services.collection_service import CollectionService

router = APIRouter(prefix="/collections", tags=["Collections"])


# ---------------------------------------------------------------------------
# Collection CRUD
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[CollectionResponse])
async def listar_meus_collections(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CollectionResponse]:
    """Lista todos os collections onde sou membro."""
    return await CollectionService(session).listar_meus(current_user)


@router.post("/", response_model=CollectionDetailResponse, status_code=status.HTTP_201_CREATED)
async def criar_collection(
    body: CollectionCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionDetailResponse:
    """Cria um novo collection compartilhado."""
    return await CollectionService(session).criar(current_user, body)


@router.get("/{collection_id}", response_model=CollectionDetailResponse)
async def detalhe_collection(
    collection_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionDetailResponse:
    """Retorna detalhes de um collection (jogos + membros)."""
    return await CollectionService(session).detalhe(collection_id, current_user)


@router.patch("/{collection_id}", response_model=CollectionDetailResponse)
async def atualizar_collection(
    collection_id: UUID,
    body: CollectionUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionDetailResponse:
    """Atualiza nome ou descrição do collection (somente dono)."""
    return await CollectionService(session).atualizar(collection_id, body, current_user)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_collection(
    collection_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Exclui o collection e todos os seus jogos e membros (somente dono)."""
    await CollectionService(session).excluir(collection_id, current_user)


# ---------------------------------------------------------------------------
# Membros
# ---------------------------------------------------------------------------

class _ConvidarBody(CollectionCreate):
    pass


from pydantic import BaseModel

class _UserIdBody(BaseModel):
    user_id: UUID


@router.post("/{collection_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def convidar_membro(
    collection_id: UUID,
    body: _UserIdBody,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MemberResponse:
    """Convida um usuário para o collection (somente dono)."""
    return await CollectionService(session).convidar_membro(collection_id, body.user_id, current_user)


@router.delete("/{collection_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover_membro(
    collection_id: UUID,
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove um membro do collection. Dono remove qualquer um; membro pode sair."""
    await CollectionService(session).remover_membro(collection_id, user_id, current_user)


# ---------------------------------------------------------------------------
# Jogos
# ---------------------------------------------------------------------------

class _GameIdBody(BaseModel):
    game_id: UUID


@router.get("/{collection_id}/available-games", response_model=list[CollectionGameResponse])
async def jogos_disponiveis(
    collection_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CollectionGameResponse]:
    """Jogos nas bibliotecas dos membros que ainda não estão na collection."""
    return await CollectionService(session).jogos_disponiveis(collection_id, current_user)


@router.post("/{collection_id}/games", response_model=CollectionGameResponse, status_code=status.HTTP_201_CREATED)
async def adicionar_jogo(
    collection_id: UUID,
    body: _GameIdBody,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionGameResponse:
    """Adiciona um jogo ao collection (qualquer membro)."""
    return await CollectionService(session).adicionar_jogo(collection_id, body.game_id, current_user)


@router.delete("/{collection_id}/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover_jogo(
    collection_id: UUID,
    game_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove um jogo do collection. Apenas quem adicionou ou o dono pode remover."""
    await CollectionService(session).remover_jogo(collection_id, game_id, current_user)
