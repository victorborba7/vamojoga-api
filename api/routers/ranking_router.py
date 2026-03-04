from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.ranking import RankingEntry, UserStats
from api.services.ranking_service import RankingService

router = APIRouter(prefix="/ranking", tags=["Ranking"])


@router.get("/global", response_model=list[RankingEntry])
async def get_global_ranking(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[RankingEntry]:
    service = RankingService(session)
    return await service.get_global_ranking(current_user.id, limit=limit)


@router.get("/game/{game_id}", response_model=list[RankingEntry])
async def get_ranking_by_game(
    game_id: UUID,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[RankingEntry]:
    service = RankingService(session)
    return await service.get_ranking_by_game(game_id, current_user.id, limit=limit)


@router.get("/user/{user_id}", response_model=UserStats)
async def get_user_stats(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> UserStats:
    service = RankingService(session)
    return await service.get_user_stats(user_id)
