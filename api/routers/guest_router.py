from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.guest import GuestCreate, GuestResponse, GuestUpdate
from api.services.guest_service import GuestService

router = APIRouter(prefix="/guests", tags=["Guests"])


@router.post("/", response_model=GuestResponse, status_code=status.HTTP_201_CREATED)
async def create_guest(
    data: GuestCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GuestResponse:
    return await GuestService(session).create_guest(data, current_user)


@router.get("/", response_model=list[GuestResponse])
async def list_guests(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[GuestResponse]:
    return await GuestService(session).list_guests(current_user)


@router.patch("/{guest_id}", response_model=GuestResponse)
async def update_guest(
    guest_id: UUID,
    data: GuestUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GuestResponse:
    return await GuestService(session).update_guest(guest_id, data, current_user)


@router.delete("/{guest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guest(
    guest_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    await GuestService(session).delete_guest(guest_id, current_user)
