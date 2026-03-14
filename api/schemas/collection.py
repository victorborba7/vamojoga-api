from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class CollectionCreate(BaseModel):
    name: str
    description: str | None = None


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class MemberResponse(BaseModel):
    user_id: UUID
    username: str
    full_name: str | None = None
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class CollectionGameResponse(BaseModel):
    game_id: UUID
    name: str
    bgg_id: int | None = None
    image_url: str | None = None
    bayes_rating: float | None = None
    year: int | None = None
    added_by: UUID
    added_by_username: str | None = None
    added_at: datetime

    model_config = {"from_attributes": True}


class CollectionResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    owner_id: UUID
    created_at: datetime
    member_count: int = 0
    game_count: int = 0

    model_config = {"from_attributes": True}


class CollectionDetailResponse(CollectionResponse):
    members: list[MemberResponse] = []
    games: list[CollectionGameResponse] = []
