from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.guest import Guest
from api.models.guest_invite_token import GuestInviteToken
from api.models.match_player import MatchPlayer


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

    async def get_owner_ids_by_guest_email(self, email: str) -> list[UUID]:
        normalized_email = email.lower().strip()
        result = await self.session.execute(
            select(Guest.owner_id).where(func.lower(Guest.email) == normalized_email)
        )
        return list({row[0] for row in result.all()})

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

    async def merge_guest_history_into_user_by_email(self, email: str, user_id: UUID) -> dict[str, int]:
        normalized_email = email.lower().strip()

        guests_result = await self.session.execute(
            select(Guest.id).where(func.lower(Guest.email) == normalized_email)
        )
        guest_ids = [row[0] for row in guests_result.all()]
        if not guest_ids:
            return {"matched_guests": 0, "updated_players": 0, "deleted_duplicates": 0}

        players_result = await self.session.execute(
            select(MatchPlayer.id, MatchPlayer.match_id, MatchPlayer.created_at)
            .where(MatchPlayer.guest_id.in_(guest_ids))
            .order_by(MatchPlayer.match_id, MatchPlayer.created_at, MatchPlayer.id)
        )
        guest_players = players_result.all()
        if not guest_players:
            return {"matched_guests": len(guest_ids), "updated_players": 0, "deleted_duplicates": 0}

        match_ids = list({row.match_id for row in guest_players})
        existing_user_matches_result = await self.session.execute(
            select(MatchPlayer.match_id)
            .where(
                MatchPlayer.user_id == user_id,
                MatchPlayer.match_id.in_(match_ids),
            )
        )
        existing_user_matches = {row[0] for row in existing_user_matches_result.all()}

        duplicate_ids: list[UUID] = []
        to_update_ids: list[UUID] = []
        first_player_by_match: dict[UUID, UUID] = {}

        for row in guest_players:
            if row.match_id in existing_user_matches:
                duplicate_ids.append(row.id)
                continue

            if row.match_id not in first_player_by_match:
                first_player_by_match[row.match_id] = row.id
                to_update_ids.append(row.id)
            else:
                # Same user would appear more than once in the same match after merge.
                duplicate_ids.append(row.id)

        deleted_duplicates = 0
        if duplicate_ids:
            delete_result = await self.session.execute(
                delete(MatchPlayer).where(MatchPlayer.id.in_(duplicate_ids))
            )
            deleted_duplicates = int(delete_result.rowcount or 0)

        updated_players = 0
        if to_update_ids:
            update_result = await self.session.execute(
                update(MatchPlayer)
                .where(MatchPlayer.id.in_(to_update_ids))
                .values(
                    user_id=user_id,
                    guest_id=None,
                    scores_submitted=True,
                    scores_submitted_at=func.coalesce(MatchPlayer.scores_submitted_at, func.now()),
                )
            )
            updated_players = int(update_result.rowcount or 0)

        await self.session.commit()

        return {
            "matched_guests": len(guest_ids),
            "updated_players": updated_players,
            "deleted_duplicates": deleted_duplicates,
        }
