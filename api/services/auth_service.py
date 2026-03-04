from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.security import create_access_token, hash_password, verify_password
from api.models.user import User
from api.repositories.user_repository import UserRepository
from api.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = UserRepository(session)

    async def register(self, data: UserCreate) -> UserResponse:
        existing_email = await self.repository.get_by_email(data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já cadastrado",
            )

        existing_username = await self.repository.get_by_username(data.username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username já cadastrado",
            )

        user = User(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )
        created_user = await self.repository.create(user)
        return UserResponse.model_validate(created_user)

    async def login(self, data: UserLogin) -> TokenResponse:
        # Support login by e-mail or username
        if "@" in data.identifier:
            user = await self.repository.get_by_email(data.identifier.lower().strip())
        else:
            user = await self.repository.get_by_username(data.identifier.strip())

        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário inativo",
            )

        token = create_access_token(user.id)
        return TokenResponse(access_token=token)
