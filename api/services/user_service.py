from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories.user_repository import UserRepository
from api.schemas.user import UserResponse


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = UserRepository(session)

    async def get_user(self, user_id: UUID) -> UserResponse:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )
        return UserResponse.model_validate(user)

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[UserResponse]:
        users = await self.repository.list_all(skip=skip, limit=limit)
        return [UserResponse.model_validate(u) for u in users]

    async def search_users(self, query: str, limit: int = 10) -> list[UserResponse]:
        users = await self.repository.search_by_name(query=query, limit=limit)
        return [UserResponse.model_validate(u) for u in users]
