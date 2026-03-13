from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.game import Game
from api.models.user import User
from api.repositories.friendship_repository import FriendshipRepository
from api.repositories.game_repository import GameRepository
from api.repositories.library_repository import LibraryRepository
from api.repositories.user_repository import UserRepository
from api.repositories.wishlist_repository import WishlistRepository
from api.schemas.game import GameResponse
from api.schemas.library import WishlistEntryResponse, WishlistVisibilityUpdate


def _game_to_response(game: Game) -> GameResponse:
    return GameResponse.model_validate(game, from_attributes=True)


class WishlistService:
    def __init__(self, session: AsyncSession) -> None:
        self.wishlist_repo = WishlistRepository(session)
        self.game_repo = GameRepository(session)
        self.library_repo = LibraryRepository(session)
        self.friendship_repo = FriendshipRepository(session)
        self.user_repo = UserRepository(session)

    async def _get_friend_ids(self, user_id: UUID) -> list[UUID]:
        friendships = await self.friendship_repo.get_friends(user_id)
        return [
            f.addressee_id if f.requester_id == user_id else f.requester_id
            for f in friendships
        ]

    async def _friends_who_own(
        self, current_user: User, game_id: UUID
    ) -> list[str]:
        """Retorna usernames de amigos do usuário que possuem o jogo."""
        friend_ids = await self._get_friend_ids(current_user.id)
        if not friend_ids:
            return []

        owner_ids = await self.library_repo.get_owners_of_game(game_id, friend_ids)
        if not owner_ids:
            return []
        users = await self.user_repo.get_by_ids(owner_ids)
        return [u.username for u in users]

    async def _batch_friends_who_own(
        self, user_id: UUID, game_ids: list[UUID]
    ) -> dict[UUID, list[str]]:
        """Retorna mapa game_id -> [usernames de amigos que possuem] em batch."""
        friend_ids = await self._get_friend_ids(user_id)
        if not friend_ids or not game_ids:
            return {gid: [] for gid in game_ids}

        # Busca todos os owners de uma vez para todos os jogos
        all_owner_ids: set[UUID] = set()
        game_owners: dict[UUID, list[UUID]] = {}
        for gid in game_ids:
            owners = await self.library_repo.get_owners_of_game(gid, friend_ids)
            game_owners[gid] = owners
            all_owner_ids.update(owners)

        # Busca todos os users em 1 query
        users_map: dict[UUID, str] = {}
        if all_owner_ids:
            users = await self.user_repo.get_by_ids(list(all_owner_ids))
            users_map = {u.id: u.username for u in users}

        return {
            gid: [users_map[uid] for uid in owners if uid in users_map]
            for gid, owners in game_owners.items()
        }

    async def add_game(
        self, user: User, game_id: UUID, is_public: bool = True
    ) -> WishlistEntryResponse:
        game = await self.game_repo.get_by_id(game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jogo não encontrado",
            )

        existing = await self.wishlist_repo.get_entry(user.id, game_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Jogo já está na sua wishlist",
            )

        entry = await self.wishlist_repo.add(user.id, game_id, is_public)
        friends_who_own = await self._friends_who_own(user, game_id)

        return WishlistEntryResponse(
            id=entry.id,
            game=_game_to_response(game),
            is_public=entry.is_public,
            added_at=entry.created_at,
            friends_who_own=friends_who_own,
        )

    async def remove_game(self, user: User, game_id: UUID) -> None:
        entry = await self.wishlist_repo.get_entry(user.id, game_id)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jogo não está na sua wishlist",
            )
        await self.wishlist_repo.remove(entry)

    async def get_my_wishlist(self, user: User) -> list[WishlistEntryResponse]:
        rows = await self.wishlist_repo.get_by_user_with_games(user.id)
        if not rows:
            return []

        game_ids = [game.id for _, game in rows]
        friends_map = await self._batch_friends_who_own(user.id, game_ids)

        return [
            WishlistEntryResponse(
                id=entry.id,
                game=_game_to_response(game),
                is_public=entry.is_public,
                added_at=entry.created_at,
                friends_who_own=friends_map.get(game.id, []),
            )
            for entry, game in rows
        ]

    async def get_user_wishlist(
        self, requesting_user: User, owner_id: UUID
    ) -> list[WishlistEntryResponse]:
        """
        Retorna a wishlist de outro usuário.
        Só exibe itens públicos, a menos que o solicitante seja o dono.
        """
        public_only = requesting_user.id != owner_id
        rows = await self.wishlist_repo.get_by_user_with_games(
            owner_id, public_only=public_only
        )
        if not rows:
            return []

        game_ids = [game.id for _, game in rows]
        friends_map = await self._batch_friends_who_own(
            requesting_user.id, game_ids
        )

        return [
            WishlistEntryResponse(
                id=entry.id,
                game=_game_to_response(game),
                is_public=entry.is_public,
                added_at=entry.created_at,
                friends_who_own=friends_map.get(game.id, []),
            )
            for entry, game in rows
        ]

    async def update_visibility(
        self, user: User, game_id: UUID, data: WishlistVisibilityUpdate
    ) -> WishlistEntryResponse:
        entry = await self.wishlist_repo.get_entry(user.id, game_id)
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jogo não está na sua wishlist",
            )
        game = await self.game_repo.get_by_id(game_id)
        if not game:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jogo não encontrado")

        entry = await self.wishlist_repo.update_visibility(entry, data.is_public)
        friends_who_own = await self._friends_who_own(user, game.id)

        return WishlistEntryResponse(
            id=entry.id,
            game=_game_to_response(game),
            is_public=entry.is_public,
            added_at=entry.created_at,
            friends_who_own=friends_who_own,
        )
