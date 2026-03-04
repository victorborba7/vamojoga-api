from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.user import UserResponse
from api.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/search/", response_model=list[UserResponse])
async def search_users(
    q: str = "",
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> list[UserResponse]:
    service = UserService(session)
    return await service.search_users(query=q, limit=limit)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> UserResponse:
    service = UserService(session)
    return await service.get_user(user_id)


@router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> list[UserResponse]:
    service = UserService(session)
    return await service.list_users(skip=skip, limit=limit)
