from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import settings
from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.repositories.push_repository import PushRepository

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class PushSubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


@router.get("/vapid-public-key")
async def get_vapid_public_key() -> dict[str, str]:
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(
    body: PushSubscribeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    repo = PushRepository(session)
    await repo.upsert(current_user.id, body.endpoint, body.p256dh, body.auth)


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    body: PushUnsubscribeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    repo = PushRepository(session)
    await repo.delete_by_endpoint(body.endpoint)
