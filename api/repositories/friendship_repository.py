from uuid import UUID

from sqlalchemy import or_, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.friendship import Friendship


class FriendshipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, friendship: Friendship) -> Friendship:
        self.session.add(friendship)
        await self.session.commit()
        await self.session.refresh(friendship)
        return friendship

    async def get_by_id(self, friendship_id: UUID) -> Friendship | None:
        statement = select(Friendship).where(Friendship.id == friendship_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_between_users(
        self, user_a: UUID, user_b: UUID
    ) -> Friendship | None:
        statement = select(Friendship).where(
            or_(
                and_(
                    Friendship.requester_id == user_a,
                    Friendship.addressee_id == user_b,
                ),
                and_(
                    Friendship.requester_id == user_b,
                    Friendship.addressee_id == user_a,
                ),
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_friends(self, user_id: UUID) -> list[Friendship]:
        statement = select(Friendship).where(
            and_(
                or_(
                    Friendship.requester_id == user_id,
                    Friendship.addressee_id == user_id,
                ),
                Friendship.status == "accepted",
            )
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_pending_received(self, user_id: UUID) -> list[Friendship]:
        statement = select(Friendship).where(
            and_(
                Friendship.addressee_id == user_id,
                Friendship.status == "pending",
            )
        ).order_by(Friendship.created_at.desc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_pending_sent(self, user_id: UUID) -> list[Friendship]:
        statement = select(Friendship).where(
            and_(
                Friendship.requester_id == user_id,
                Friendship.status == "pending",
            )
        ).order_by(Friendship.created_at.desc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update_status(self, friendship: Friendship, status: str) -> Friendship:
        from datetime import datetime, timezone
        friendship.status = status
        friendship.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add(friendship)
        await self.session.commit()
        await self.session.refresh(friendship)
        return friendship

    async def delete(self, friendship: Friendship) -> None:
        await self.session.delete(friendship)
        await self.session.commit()
