import uuid
from uuid import UUID

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.collection import Collection, CollectionGame, CollectionMember
from api.models.game import Game
from api.models.user import User


class CollectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    async def create(self, collection: Collection) -> Collection:
        self.session.add(collection)
        await self.session.flush()
        await self.session.refresh(collection)
        return collection

    async def get_by_id(self, collection_id: UUID) -> Collection | None:
        result = await self.session.execute(
            select(Collection).where(Collection.id == collection_id)
        )
        return result.scalar_one_or_none()

    async def update(self, collection: Collection) -> Collection:
        self.session.add(collection)
        await self.session.flush()
        await self.session.refresh(collection)
        return collection

    async def delete(self, collection: Collection) -> None:
        await self.session.delete(collection)
        await self.session.flush()

    # ------------------------------------------------------------------
    # Members
    # ------------------------------------------------------------------

    async def get_members(self, collection_id: UUID) -> list[CollectionMember]:
        result = await self.session.execute(
            select(CollectionMember).where(CollectionMember.collection_id == collection_id)
        )
        return list(result.scalars().all())

    async def get_members_with_users(
        self, collection_id: UUID
    ) -> list[tuple[CollectionMember, User]]:
        """Retorna membros com usuários já carregados (1 query)."""
        result = await self.session.execute(
            select(CollectionMember, User)
            .join(User, User.id == CollectionMember.user_id)
            .where(CollectionMember.collection_id == collection_id)
        )
        return list(result.tuples().all())

    async def get_games_with_details(
        self, collection_id: UUID
    ) -> list[tuple[CollectionGame, Game, str | None]]:
        """Retorna jogos com Game + username de quem adicionou (1 query)."""
        result = await self.session.execute(
            select(CollectionGame, Game, User.username)
            .join(Game, Game.id == CollectionGame.game_id)
            .outerjoin(User, User.id == CollectionGame.added_by)
            .where(CollectionGame.collection_id == collection_id)
        )
        return list(result.tuples().all())

    async def get_member(self, collection_id: UUID, user_id: UUID) -> CollectionMember | None:
        result = await self.session.execute(
            select(CollectionMember).where(
                and_(
                    CollectionMember.collection_id == collection_id,
                    CollectionMember.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def add_member(self, member: CollectionMember) -> CollectionMember:
        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def remove_member(self, member: CollectionMember) -> None:
        await self.session.delete(member)
        await self.session.flush()

    async def get_collections_for_user(self, user_id: UUID) -> list[Collection]:
        """Retorna todos os collections onde o usuário é membro (inclui os que criou)."""
        result = await self.session.execute(
            select(Collection)
            .join(CollectionMember, CollectionMember.collection_id == Collection.id)
            .where(CollectionMember.user_id == user_id)
            .order_by(Collection.created_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Games
    # ------------------------------------------------------------------

    async def get_games(self, collection_id: UUID) -> list[CollectionGame]:
        result = await self.session.execute(
            select(CollectionGame).where(CollectionGame.collection_id == collection_id)
        )
        return list(result.scalars().all())

    async def get_game(self, collection_id: UUID, game_id: UUID) -> CollectionGame | None:
        result = await self.session.execute(
            select(CollectionGame).where(
                and_(
                    CollectionGame.collection_id == collection_id,
                    CollectionGame.game_id == game_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def add_game(self, game: CollectionGame) -> CollectionGame:
        self.session.add(game)
        await self.session.flush()
        await self.session.refresh(game)
        return game

    async def remove_game(self, game: CollectionGame) -> None:
        await self.session.delete(game)
        await self.session.flush()

    async def count_members(self, collection_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(CollectionMember)
            .where(CollectionMember.collection_id == collection_id)
        )
        return result.scalar_one() or 0

    async def count_games(self, collection_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(CollectionGame)
            .where(CollectionGame.collection_id == collection_id)
        )
        return result.scalar_one() or 0

    async def batch_counts(
        self, collection_ids: list[UUID]
    ) -> dict[UUID, tuple[int, int]]:
        """Retorna {collection_id: (member_count, game_count)} em 2 queries."""
        if not collection_ids:
            return {}

        m_result = await self.session.execute(
            select(CollectionMember.collection_id, func.count())
            .where(CollectionMember.collection_id.in_(collection_ids))
            .group_by(CollectionMember.collection_id)
        )
        member_counts = dict(m_result.all())

        g_result = await self.session.execute(
            select(CollectionGame.collection_id, func.count())
            .where(CollectionGame.collection_id.in_(collection_ids))
            .group_by(CollectionGame.collection_id)
        )
        game_counts = dict(g_result.all())

        return {
            cid: (member_counts.get(cid, 0), game_counts.get(cid, 0))
            for cid in collection_ids
        }

    async def bulk_delete_members(self, collection_id: UUID) -> None:
        await self.session.execute(
            delete(CollectionMember)
            .where(CollectionMember.collection_id == collection_id)
        )

    async def bulk_delete_games(self, collection_id: UUID) -> None:
        await self.session.execute(
            delete(CollectionGame)
            .where(CollectionGame.collection_id == collection_id)
        )
