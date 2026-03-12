import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.core.security import create_access_token, hash_password, verify_password
from api.core.email import send_password_reset_email, send_verification_email
from api.models.user import User
from api.models.password_reset import PasswordResetToken
from api.models.email_verification import EmailVerificationToken
from api.repositories.user_repository import UserRepository
from api.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
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

        # Send verification email
        await self._send_verification_email(created_user)

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

    async def forgot_password(self, email: str) -> None:
        """Generate a reset token and send email. Always returns success (no leak)."""
        user = await self.repository.get_by_email(email.lower().strip())
        if not user:
            # Don't reveal whether the email exists
            return

        # Generate secure token
        token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)

        reset = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
        )
        self.session.add(reset)
        await self.session.commit()

        try:
            send_password_reset_email(user.email, user.username, token)
        except Exception:
            logger.warning("Failed to send reset email to %s", email)

    async def reset_password(self, token: str, new_password: str) -> None:
        """Validate token and update password."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token == token,
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > now,
        )
        result = await self.session.execute(stmt)
        reset = result.scalar_one_or_none()

        if not reset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido ou expirado",
            )

        user = await self.repository.get_by_id(reset.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )

        user.hashed_password = hash_password(new_password)
        user.updated_at = now
        self.session.add(user)

        reset.used = True
        self.session.add(reset)

        await self.session.commit()

    async def _send_verification_email(self, user: User) -> None:
        """Create a verification token and send the email."""
        token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)

        verification = EmailVerificationToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
        )
        self.session.add(verification)
        await self.session.commit()

        try:
            send_verification_email(user.email, user.username, token)
        except Exception:
            logger.warning("Failed to send verification email to %s", user.email)

    async def verify_email(self, token: str) -> None:
        """Validate verification token and mark email as verified."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.token == token,
            EmailVerificationToken.used == False,  # noqa: E712
            EmailVerificationToken.expires_at > now,
        )
        result = await self.session.execute(stmt)
        verification = result.scalar_one_or_none()

        if not verification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido ou expirado",
            )

        user = await self.repository.get_by_id(verification.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )

        user.email_verified = True
        user.updated_at = now
        self.session.add(user)

        verification.used = True
        self.session.add(verification)

        await self.session.commit()

    async def resend_verification(self, user_id) -> None:
        """Resend verification email for the current user."""
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )

        if user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="E-mail já verificado",
            )

        await self._send_verification_email(user)
