from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FriendshipResponse(BaseModel):
    id: UUID
    requester_id: UUID
    requester_username: str | None = None
    addressee_id: UUID
    addressee_username: str | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FriendResponse(BaseModel):
    friendship_id: UUID
    user_id: UUID
    username: str
    full_name: str | None = None
    since: datetime
