from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.guest import Guest
from api.models.guest_invite_token import GuestInviteToken


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class GuestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, guest: Guest) -> Guest:
        self.session.add(guest)
        await self.session.commit()
        await self.session.refresh(guest)
        return guest

    async def get_by_id(self, guest_id: UUID) -> Guest | None:
        result = await self.session.execute(select(Guest).where(Guest.id == guest_id))
        return result.scalar_one_or_none()

    async def get_by_ids(self, guest_ids: list[UUID]) -> list[Guest]:
        if not guest_ids:
            return []
        result = await self.session.execute(select(Guest).where(Guest.id.in_(guest_ids)))
        return list(result.scalars().all())

    async def list_by_owner(self, owner_id: UUID) -> list[Guest]:
        result = await self.session.execute(
            select(Guest)
            .where(Guest.owner_id == owner_id)
            .order_by(Guest.name)
        )
        return list(result.scalars().all())

    async def update(self, guest: Guest) -> Guest:
        guest.updated_at = _utcnow()
        self.session.add(guest)
        await self.session.commit()
        await self.session.refresh(guest)
        return guest

    async def delete(self, guest: Guest) -> None:
        await self.session.delete(guest)
        await self.session.commit()

    async def create_invite_token(self, token: GuestInviteToken) -> GuestInviteToken:
        self.session.add(token)
        await self.session.commit()
        await self.session.refresh(token)
        return token

    async def get_invite_token(self, token: str) -> GuestInviteToken | None:
        result = await self.session.execute(
            select(GuestInviteToken).where(GuestInviteToken.token == token)
        )
        return result.scalar_one_or_none()

    async def mark_invite_as_used(self, invite: GuestInviteToken) -> GuestInviteToken:
        invite.used = True
        self.session.add(invite)
        await self.session.commit()
        await self.session.refresh(invite)
        return invite
