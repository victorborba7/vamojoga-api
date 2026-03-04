import uuid
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.collection import Collection, CollectionMembro, CollectionJogo


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
            select(CollectionMembro).where(CollectionMembro.collection_id == collection_id)
        )
        return len(result.scalars().all())

    async def count_jogos(self, collection_id: UUID) -> int:
        result = await self.session.execute(
            select(CollectionJogo).where(CollectionJogo.collection_id == collection_id)
        )
        return len(result.scalars().all())
