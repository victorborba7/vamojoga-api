import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.core.security import create_access_token, hash_password, verify_password
from api.core.email import send_password_reset_email, send_verification_email
from api.models.user import User
from api.models.friendship import Friendship
from api.models.password_reset import PasswordResetToken
from api.models.email_verification import EmailVerificationToken
from api.repositories.friendship_repository import FriendshipRepository
from api.repositories.guest_repository import GuestRepository
from api.repositories.user_repository import UserRepository
from api.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = UserRepository(session)
        self.guest_repository = GuestRepository(session)
        self.friendship_repository = FriendshipRepository(session)

    async def register(self, data: UserCreate) -> UserResponse:
        invite = None
        if data.invite_token:
            invite = await self.guest_repository.get_invite_token(data.invite_token)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if not invite or invite.used or invite.expires_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Convite invalido ou expirado",
                )

            invite_email = invite.email.lower().strip()
            request_email = str(data.email).lower().strip()
            if invite_email != request_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Este convite pertence a outro e-mail",
                )

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

        owner_ids = await self.guest_repository.get_owner_ids_by_guest_email(created_user.email)

        merge_result = await self.guest_repository.merge_guest_history_into_user_by_email(
            email=created_user.email,
            user_id=created_user.id,
        )

        friendship_result = await self._link_guest_owners_as_friends(
            new_user_id=created_user.id,
            owner_ids=owner_ids,
        )
        if merge_result["updated_players"] > 0 or merge_result["deleted_duplicates"] > 0:
            logger.info(
                "Guest history merged on register for user_id=%s email=%s guests=%s updated=%s deleted_duplicates=%s",
                created_user.id,
                created_user.email,
                merge_result["matched_guests"],
                merge_result["updated_players"],
                merge_result["deleted_duplicates"],
            )
        if friendship_result["created"] > 0 or friendship_result["updated"] > 0:
            logger.info(
                "Guest owners linked as friends for user_id=%s created=%s updated=%s",
                created_user.id,
                friendship_result["created"],
                friendship_result["updated"],
            )

        if invite is not None:
            await self.guest_repository.mark_invite_as_used(invite)

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

    async def _link_guest_owners_as_friends(self, new_user_id: UUID, owner_ids: list[UUID]) -> dict[str, int]:
        created = 0
        updated = 0
        for owner_id in set(owner_ids):
            if owner_id == new_user_id:
                continue

            existing = await self.friendship_repository.get_between_users(new_user_id, owner_id)
            if not existing:
                await self.friendship_repository.create(
                    Friendship(
                        requester_id=owner_id,
                        addressee_id=new_user_id,
                        status="accepted",
                    )
                )
                created += 1
            elif existing.status != "accepted":
                await self.friendship_repository.update_status(existing, "accepted")
                updated += 1

        return {"created": created, "updated": updated}
