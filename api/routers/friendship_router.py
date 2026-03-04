from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.friendship import FriendResponse, FriendshipResponse
from api.services.friendship_service import FriendshipService

router = APIRouter(prefix="/friends", tags=["Friends"])


@router.post("/request/{addressee_id}", response_model=FriendshipResponse)
async def send_friend_request(
    addressee_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FriendshipResponse:
    service = FriendshipService(session)
    return await service.send_request(current_user, addressee_id)


@router.post("/{friendship_id}/accept", response_model=FriendshipResponse)
async def accept_friend_request(
    friendship_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FriendshipResponse:
    service = FriendshipService(session)
    return await service.accept_request(friendship_id, current_user)


@router.post("/{friendship_id}/reject", response_model=FriendshipResponse)
async def reject_friend_request(
    friendship_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FriendshipResponse:
    service = FriendshipService(session)
    return await service.reject_request(friendship_id, current_user)


@router.delete("/{friendship_id}", status_code=204)
async def remove_friend(
    friendship_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    service = FriendshipService(session)
    await service.remove_friend(friendship_id, current_user)


@router.get("/", response_model=list[FriendResponse])
async def get_friends(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[FriendResponse]:
    service = FriendshipService(session)
    return await service.get_friends(current_user.id)


@router.get("/pending/received", response_model=list[FriendshipResponse])
async def get_pending_received(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[FriendshipResponse]:
    service = FriendshipService(session)
    return await service.get_pending_received(current_user.id)


@router.get("/pending/sent", response_model=list[FriendshipResponse])
async def get_pending_sent(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[FriendshipResponse]:
    service = FriendshipService(session)
    return await service.get_pending_sent(current_user.id)
