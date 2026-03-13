import asyncio
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.friendship import Friendship
from api.models.user import User
from api.repositories.friendship_repository import FriendshipRepository
from api.repositories.user_repository import UserRepository
from api.schemas.friendship import FriendResponse, FriendshipResponse
from api.services.push_service import PushService


class FriendshipService:
    def __init__(self, session: AsyncSession) -> None:
        self.friendship_repo = FriendshipRepository(session)
        self.user_repo = UserRepository(session)
        self.push_service = PushService(session)

    async def send_request(
        self, requester: User, addressee_id: UUID
    ) -> FriendshipResponse:
        if requester.id == addressee_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Você não pode adicionar a si mesmo",
            )

        addressee = await self.user_repo.get_by_id(addressee_id)
        if not addressee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )

        existing = await self.friendship_repo.get_between_users(
            requester.id, addressee_id
        )
        if existing:
            if existing.status == "accepted":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Vocês já são amigos",
                )
            if existing.status == "pending":
                # If the other person already sent a request, accept it
                if existing.requester_id == addressee_id:
                    return await self._accept(existing, requester, addressee)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Solicitação já enviada",
                )
            if existing.status == "rejected":
                # Allow re-sending
                await self.friendship_repo.delete(existing)

        friendship = Friendship(
            requester_id=requester.id,
            addressee_id=addressee_id,
        )
        created = await self.friendship_repo.create(friendship)

        # Push notification to addressee (fire-and-forget)
        asyncio.create_task(
            self.push_service.send_to_user(
                addressee_id,
                "Nova solicitação de amizade",
                f"{requester.username} quer ser seu amigo no VamoJogá!",
                "/social",
            )
        )

        return FriendshipResponse(
            id=created.id,
            requester_id=created.requester_id,
            requester_username=requester.username,
            addressee_id=created.addressee_id,
            addressee_username=addressee.username,
            status=created.status,
            created_at=created.created_at,
        )

    async def accept_request(
        self, friendship_id: UUID, current_user: User
    ) -> FriendshipResponse:
        friendship = await self.friendship_repo.get_by_id(friendship_id)
        if not friendship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitação não encontrada",
            )
        if friendship.addressee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não pode aceitar essa solicitação",
            )
        if friendship.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solicitação já processada",
            )

        requester = await self.user_repo.get_by_id(friendship.requester_id)
        addressee = current_user
        return await self._accept(friendship, addressee, requester)

    async def _accept(
        self, friendship: Friendship, current_user: User, other_user: User | None
    ) -> FriendshipResponse:
        updated = await self.friendship_repo.update_status(friendship, "accepted")
        return FriendshipResponse(
            id=updated.id,
            requester_id=updated.requester_id,
            requester_username=other_user.username if other_user and updated.requester_id == other_user.id else current_user.username,
            addressee_id=updated.addressee_id,
            addressee_username=current_user.username if updated.addressee_id == current_user.id else (other_user.username if other_user else None),
            status=updated.status,
            created_at=updated.created_at,
        )

    async def reject_request(
        self, friendship_id: UUID, current_user: User
    ) -> FriendshipResponse:
        friendship = await self.friendship_repo.get_by_id(friendship_id)
        if not friendship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitação não encontrada",
            )
        if friendship.addressee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não pode recusar essa solicitação",
            )
        if friendship.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solicitação já processada",
            )

        updated = await self.friendship_repo.update_status(friendship, "rejected")
        requester = await self.user_repo.get_by_id(friendship.requester_id)
        return FriendshipResponse(
            id=updated.id,
            requester_id=updated.requester_id,
            requester_username=requester.username if requester else None,
            addressee_id=updated.addressee_id,
            addressee_username=current_user.username,
            status=updated.status,
            created_at=updated.created_at,
        )

    async def remove_friend(
        self, friendship_id: UUID, current_user: User
    ) -> None:
        friendship = await self.friendship_repo.get_by_id(friendship_id)
        if not friendship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Amizade não encontrada",
            )
        if (
            friendship.requester_id != current_user.id
            and friendship.addressee_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não faz parte dessa amizade",
            )
        await self.friendship_repo.delete(friendship)

    async def get_friends(self, user_id: UUID) -> list[FriendResponse]:
        friendships = await self.friendship_repo.get_friends(user_id)
        if not friendships:
            return []

        # Batch fetch all friend users in one query
        friend_ids = [
            f.addressee_id if f.requester_id == user_id else f.requester_id
            for f in friendships
        ]
        users = await self.user_repo.get_by_ids(friend_ids)
        users_map = {u.id: u for u in users}

        friends: list[FriendResponse] = []
        for f in friendships:
            friend_id = f.addressee_id if f.requester_id == user_id else f.requester_id
            friend_user = users_map.get(friend_id)
            if friend_user:
                friends.append(
                    FriendResponse(
                        friendship_id=f.id,
                        user_id=friend_user.id,
                        username=friend_user.username,
                        full_name=friend_user.full_name,
                        since=f.updated_at,
                    )
                )
        return friends

    async def get_pending_received(
        self, user_id: UUID
    ) -> list[FriendshipResponse]:
        pending = await self.friendship_repo.get_pending_received(user_id)
        if not pending:
            return []

        requester_ids = [f.requester_id for f in pending]
        users = await self.user_repo.get_by_ids(requester_ids)
        users_map = {u.id: u for u in users}

        return [
            FriendshipResponse(
                id=f.id,
                requester_id=f.requester_id,
                requester_username=users_map[f.requester_id].username if f.requester_id in users_map else None,
                addressee_id=f.addressee_id,
                status=f.status,
                created_at=f.created_at,
            )
            for f in pending
        ]

    async def get_pending_sent(
        self, user_id: UUID
    ) -> list[FriendshipResponse]:
        pending = await self.friendship_repo.get_pending_sent(user_id)
        if not pending:
            return []

        addressee_ids = [f.addressee_id for f in pending]
        users = await self.user_repo.get_by_ids(addressee_ids)
        users_map = {u.id: u for u in users}

        return [
            FriendshipResponse(
                id=f.id,
                requester_id=f.requester_id,
                addressee_id=f.addressee_id,
                addressee_username=users_map[f.addressee_id].username if f.addressee_id in users_map else None,
                status=f.status,
                created_at=f.created_at,
            )
            for f in pending
        ]
