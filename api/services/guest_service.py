import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.email import send_guest_invite_email
from api.models.guest import Guest
from api.models.guest_invite_token import GuestInviteToken
from api.models.user import User
from api.repositories.guest_repository import GuestRepository
from api.schemas.guest import GuestCreate, GuestResponse, GuestUpdate
from api.schemas.user import GuestInviteValidationResponse

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class GuestService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = GuestRepository(session)

    async def create_guest(self, data: GuestCreate, current_user: User) -> GuestResponse:
        guest = Guest(
            owner_id=current_user.id,
            name=data.name.strip(),
            email=(str(data.email).lower().strip() if data.email else None),
        )
        guest = await self.repository.create(guest)

        if guest.email:
            await self._send_invite(guest)

        return GuestResponse.model_validate(guest)

    async def list_guests(self, current_user: User) -> list[GuestResponse]:
        guests = await self.repository.list_by_owner(current_user.id)
        return [GuestResponse.model_validate(g) for g in guests]

    async def update_guest(self, guest_id: UUID, data: GuestUpdate, current_user: User) -> GuestResponse:
        guest = await self.repository.get_by_id(guest_id)
        if not guest or guest.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convidado nao encontrado")

        if data.name is not None:
            guest.name = data.name.strip()

        email_changed = False
        if data.email is not None:
            normalized = str(data.email).lower().strip() if data.email else None
            email_changed = normalized != guest.email
            guest.email = normalized

        guest = await self.repository.update(guest)

        if email_changed and guest.email:
            await self._send_invite(guest)

        return GuestResponse.model_validate(guest)

    async def delete_guest(self, guest_id: UUID, current_user: User) -> None:
        guest = await self.repository.get_by_id(guest_id)
        if not guest or guest.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convidado nao encontrado")

        await self.repository.delete(guest)

    async def _send_invite(self, guest: Guest) -> None:
        token = secrets.token_urlsafe(48)
        invite = GuestInviteToken(
            guest_id=guest.id,
            email=guest.email or "",
            token=token,
            expires_at=_utcnow() + timedelta(days=7),
        )
        await self.repository.create_invite_token(invite)

        try:
            send_guest_invite_email(
                to=guest.email or "",
                guest_name=guest.name,
                token=token,
            )
        except Exception:
            logger.warning("Falha ao enviar convite de cadastro para convidado %s", guest.id)

    async def validate_invite(self, token: str) -> GuestInviteValidationResponse:
        invite = await self.repository.get_invite_token(token)
        now = _utcnow()
        if not invite or invite.used or invite.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Convite invalido ou expirado",
            )

        guest = await self.repository.get_by_id(invite.guest_id)
        if not guest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Convidado nao encontrado",
            )

        return GuestInviteValidationResponse(
            guest_name=guest.name,
            email=invite.email,
            expires_at=invite.expires_at,
            is_valid=True,
        )
