from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.game import Game
from api.models.user_wishlist import UserWishlist


class WishlistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self, user_id: UUID, game_id: UUID, is_public: bool = True
    ) -> UserWishlist:
        entry = UserWishlist(user_id=user_id, game_id=game_id, is_public=is_public)
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def remove(self, entry: UserWishlist) -> None:
        await self.session.delete(entry)
        await self.session.commit()

    async def get_entry(
        self, user_id: UUID, game_id: UUID
    ) -> UserWishlist | None:
        stmt = select(UserWishlist).where(
            UserWishlist.user_id == user_id,
            UserWishlist.game_id == game_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, entry_id: UUID) -> UserWishlist | None:
        stmt = select(UserWishlist).where(UserWishlist.id == entry_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: UUID) -> list[UserWishlist]:
        stmt = (
            select(UserWishlist)
            .where(UserWishlist.user_id == user_id)
            .order_by(UserWishlist.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user_with_games(
        self, user_id: UUID, public_only: bool = False
    ) -> list[tuple[UserWishlist, Game]]:
        """Retorna wishlist com jogos já carregados (1 query)."""
        stmt = (
            select(UserWishlist, Game)
            .join(Game, Game.id == UserWishlist.game_id)
            .where(UserWishlist.user_id == user_id)
            .order_by(UserWishlist.created_at.desc())
        )
        if public_only:
            stmt = stmt.where(UserWishlist.is_public.is_(True))
        result = await self.session.execute(stmt)
        return list(result.tuples().all())

    async def get_public_by_user(self, user_id: UUID) -> list[UserWishlist]:
        """Wishlist pública de outro usuário (para compartilhamento)."""
        stmt = (
            select(UserWishlist)
            .where(
                UserWishlist.user_id == user_id,
                UserWishlist.is_public.is_(True),
            )
            .order_by(UserWishlist.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_visibility(
        self, entry: UserWishlist, is_public: bool
    ) -> UserWishlist:
        entry.is_public = is_public
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry
