from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.push_subscription import PushSubscription


class PushRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self, user_id: UUID, endpoint: str, p256dh: str, auth: str
    ) -> PushSubscription:
        stmt = (
            insert(PushSubscription)
            .values(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
            .on_conflict_do_update(
                index_elements=["endpoint"],
                set_={"user_id": user_id, "p256dh": p256dh, "auth": auth},
            )
            .returning(PushSubscription)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one()

    async def delete_by_endpoint(self, endpoint: str) -> None:
        await self.session.execute(
            delete(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
        await self.session.commit()

    async def get_by_user(self, user_id: UUID) -> list[PushSubscription]:
        result = await self.session.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
        return list(result.scalars().all())
