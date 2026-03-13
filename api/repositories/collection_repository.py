import uuid
from uuid import UUID

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.collection import Collection, CollectionJogo, CollectionMembro
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
    # Membros
    # ------------------------------------------------------------------

    async def get_membros(self, collection_id: UUID) -> list[CollectionMembro]:
        result = await self.session.execute(
            select(CollectionMembro).where(CollectionMembro.collection_id == collection_id)
        )
        return list(result.scalars().all())

    async def get_membros_with_users(
        self, collection_id: UUID
    ) -> list[tuple[CollectionMembro, User]]:
        """Retorna membros com usuários já carregados (1 query)."""
        result = await self.session.execute(
            select(CollectionMembro, User)
            .join(User, User.id == CollectionMembro.user_id)
            .where(CollectionMembro.collection_id == collection_id)
        )
        return list(result.tuples().all())

    async def get_jogos_with_details(
        self, collection_id: UUID
    ) -> list[tuple[CollectionJogo, Game, str | None]]:
        """Retorna jogos com Game + username de quem adicionou (1 query)."""
        result = await self.session.execute(
            select(CollectionJogo, Game, User.username)
            .join(Game, Game.id == CollectionJogo.game_id)
            .outerjoin(User, User.id == CollectionJogo.added_by)
            .where(CollectionJogo.collection_id == collection_id)
        )
        return list(result.tuples().all())

    async def get_membro(self, collection_id: UUID, user_id: UUID) -> CollectionMembro | None:
        result = await self.session.execute(
            select(CollectionMembro).where(
                and_(
                    CollectionMembro.collection_id == collection_id,
                    CollectionMembro.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def add_membro(self, membro: CollectionMembro) -> CollectionMembro:
        self.session.add(membro)
        await self.session.flush()
        await self.session.refresh(membro)
        return membro

    async def remove_membro(self, membro: CollectionMembro) -> None:
        await self.session.delete(membro)
        await self.session.flush()

    async def get_collections_do_usuario(self, user_id: UUID) -> list[Collection]:
        """Retorna todos os collections onde o usuário é membro (inclui os que criou)."""
        result = await self.session.execute(
            select(Collection)
            .join(CollectionMembro, CollectionMembro.collection_id == Collection.id)
            .where(CollectionMembro.user_id == user_id)
            .order_by(Collection.created_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Jogos
    # ------------------------------------------------------------------

    async def get_jogos(self, collection_id: UUID) -> list[CollectionJogo]:
        result = await self.session.execute(
            select(CollectionJogo).where(CollectionJogo.collection_id == collection_id)
        )
        return list(result.scalars().all())

    async def get_jogo(self, collection_id: UUID, game_id: UUID) -> CollectionJogo | None:
        result = await self.session.execute(
            select(CollectionJogo).where(
                and_(
                    CollectionJogo.collection_id == collection_id,
                    CollectionJogo.game_id == game_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def add_jogo(self, jogo: CollectionJogo) -> CollectionJogo:
        self.session.add(jogo)
        await self.session.flush()
        await self.session.refresh(jogo)
        return jogo

    async def remove_jogo(self, jogo: CollectionJogo) -> None:
        await self.session.delete(jogo)
        await self.session.flush()

    async def count_membros(self, collection_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(CollectionMembro)
            .where(CollectionMembro.collection_id == collection_id)
        )
        return result.scalar_one() or 0

    async def count_jogos(self, collection_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(CollectionJogo)
            .where(CollectionJogo.collection_id == collection_id)
        )
        return result.scalar_one() or 0

    async def batch_counts(
        self, collection_ids: list[UUID]
    ) -> dict[UUID, tuple[int, int]]:
        """Retorna {collection_id: (member_count, game_count)} em 2 queries."""
        if not collection_ids:
            return {}

        m_result = await self.session.execute(
            select(CollectionMembro.collection_id, func.count())
            .where(CollectionMembro.collection_id.in_(collection_ids))
            .group_by(CollectionMembro.collection_id)
        )
        member_counts = dict(m_result.all())

        g_result = await self.session.execute(
            select(CollectionJogo.collection_id, func.count())
            .where(CollectionJogo.collection_id.in_(collection_ids))
            .group_by(CollectionJogo.collection_id)
        )
        game_counts = dict(g_result.all())

        return {
            cid: (member_counts.get(cid, 0), game_counts.get(cid, 0))
            for cid in collection_ids
        }

    async def bulk_delete_membros(self, collection_id: UUID) -> None:
        await self.session.execute(
            delete(CollectionMembro)
            .where(CollectionMembro.collection_id == collection_id)
        )

    async def bulk_delete_jogos(self, collection_id: UUID) -> None:
        await self.session.execute(
            delete(CollectionJogo)
            .where(CollectionJogo.collection_id == collection_id)
        )
