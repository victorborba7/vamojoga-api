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

    async def _friends_who_own(
        self, current_user: User, game_id: UUID
    ) -> list[str]:
        """Retorna usernames de amigos do usuário que possuem o jogo."""
        friendships = await self.friendship_repo.get_friends(current_user.id)
        friend_ids = [
            f.addressee_id if f.requester_id == current_user.id else f.requester_id
            for f in friendships
        ]
        if not friend_ids:
            return []

        owner_ids = await self.library_repo.get_owners_of_game(game_id, friend_ids)
        usernames: list[str] = []
        for uid in owner_ids:
            user = await self.user_repo.get_by_id(uid)
            if user:
                usernames.append(user.username)
        return usernames

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
        entries = await self.wishlist_repo.get_by_user(user.id)
        result = []
        for entry in entries:
            game = await self.game_repo.get_by_id(entry.game_id)
            if not game:
                continue
            friends_who_own = await self._friends_who_own(user, game.id)
            result.append(
                WishlistEntryResponse(
                    id=entry.id,
                    game=_game_to_response(game),
                    is_public=entry.is_public,
                    added_at=entry.created_at,
                    friends_who_own=friends_who_own,
                )
            )
        return result

    async def get_user_wishlist(
        self, requesting_user: User, owner_id: UUID
    ) -> list[WishlistEntryResponse]:
        """
        Retorna a wishlist de outro usuário.
        Só exibe itens públicos, a menos que o solicitante seja o dono.
        """
        entries = (
            await self.wishlist_repo.get_by_user(owner_id)
            if requesting_user.id == owner_id
            else await self.wishlist_repo.get_public_by_user(owner_id)
        )
        result = []
        for entry in entries:
            game = await self.game_repo.get_by_id(entry.game_id)
            if not game:
                continue
            friends_who_own = await self._friends_who_own(requesting_user, game.id)
            result.append(
                WishlistEntryResponse(
                    id=entry.id,
                    game=_game_to_response(game),
                    is_public=entry.is_public,
                    added_at=entry.created_at,
                    friends_who_own=friends_who_own,
                )
            )
        return result

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
