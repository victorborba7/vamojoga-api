from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.match import MatchCreate, MatchResponse, PlayerScoreSubmit
from api.services.match_service import MatchService

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.post("/", response_model=MatchResponse, status_code=201)
async def create_match(
    data: MatchCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MatchResponse:
    service = MatchService(session)
    return await service.create_match(data, current_user)


@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> MatchResponse:
    service = MatchService(session)
    return await service.get_match(match_id)


@router.get("/user/{user_id}", response_model=list[MatchResponse])
async def get_user_matches(
    user_id: UUID,
    skip: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> list[MatchResponse]:
    service = MatchService(session)
    return await service.get_user_matches(user_id, skip=skip, limit=limit)


@router.post("/{match_id}/submit-scores", response_model=MatchResponse)
async def submit_own_scores(
    match_id: UUID,
    data: PlayerScoreSubmit,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MatchResponse:
    service = MatchService(session)
    return await service.submit_player_scores(match_id, current_user.id, data, current_user)


@router.post("/{match_id}/submit-scores/{user_id}", response_model=MatchResponse)
async def submit_player_scores(
    match_id: UUID,
    user_id: UUID,
    data: PlayerScoreSubmit,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MatchResponse:
    service = MatchService(session)
    return await service.submit_player_scores(match_id, user_id, data, current_user)


@router.post("/{match_id}/finalize", response_model=MatchResponse)
async def finalize_match(
    match_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MatchResponse:
    service = MatchService(session)
    return await service.finalize_match(match_id, current_user)
