from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.game import GameCreate, GameResponse, GameUpdate
from api.services.game_service import GameService

router = APIRouter(prefix="/games", tags=["Games"])


@router.post("/", response_model=GameResponse, status_code=201)
async def create_game(
    data: GameCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> GameResponse:
    service = GameService(session)
    return await service.create_game(data)


@router.get("/", response_model=list[GameResponse])
async def list_games(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> list[GameResponse]:
    service = GameService(session)
    return await service.list_games(skip=skip, limit=limit)


@router.get("/recommendations/", response_model=list[GameResponse])
async def get_recommendations(
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[GameResponse]:
    service = GameService(session)
    return await service.get_recommendations(current_user.id, limit=limit)


@router.get("/search/", response_model=list[GameResponse])
async def search_games(
    q: str = "",
    limit: int = 20,
    exclude_expansions: bool = False,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> list[GameResponse]:
    if len(q.strip()) < 1:
        return []
    service = GameService(session)
    return await service.search_games(q.strip(), limit=limit, exclude_expansions=exclude_expansions)


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> GameResponse:
    service = GameService(session)
    return await service.get_game(game_id)


@router.patch("/{game_id}", response_model=GameResponse)
async def update_game(
    game_id: UUID,
    data: GameUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> GameResponse:
    service = GameService(session)
    return await service.update_game(game_id, data)
