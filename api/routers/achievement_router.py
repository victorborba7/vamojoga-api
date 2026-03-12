from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.achievement import (
    AchievementImport,
    AchievementResponse,
    UserAchievementResponse,
)
from api.services.achievement_service import AchievementService

router = APIRouter(prefix="/achievements", tags=["Achievements"])


@router.get("/global", response_model=list[AchievementResponse])
async def get_global_achievements(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> list[AchievementResponse]:
    service = AchievementService(session)
    return await service.get_global_achievements()


@router.get("/game/{game_id}", response_model=list[AchievementResponse])
async def get_game_achievements(
    game_id: UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> list[AchievementResponse]:
    service = AchievementService(session)
    return await service.get_game_achievements(game_id)


@router.get("/me", response_model=list[UserAchievementResponse])
async def get_my_achievements(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[UserAchievementResponse]:
    service = AchievementService(session)
    return await service.get_user_achievements(current_user.id)


@router.get("/user/{user_id}", response_model=list[UserAchievementResponse])
async def get_user_achievements(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> list[UserAchievementResponse]:
    service = AchievementService(session)
    return await service.get_user_achievements(user_id)


@router.post("/import", status_code=201)
async def import_achievements(
    data: AchievementImport,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> dict:
    service = AchievementService(session)
    count = await service.import_achievements(data)
    return {"created": count}
