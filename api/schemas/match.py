from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# --- Request ---
class MatchPlayerCreate(BaseModel):
    user_id: UUID
    position: int
    score: int = 0
    is_winner: bool = False


class MatchCreate(BaseModel):
    game_id: UUID
    played_at: datetime | None = None
    notes: str | None = None
    players: list[MatchPlayerCreate] = Field(min_length=1)


# --- Response ---
class MatchPlayerResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str | None = None
    position: int
    score: int
    is_winner: bool

    model_config = {"from_attributes": True}


class MatchResponse(BaseModel):
    id: UUID
    game_id: UUID
    game_name: str | None = None
    created_by: UUID
    played_at: datetime
    notes: str | None
    players: list[MatchPlayerResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}
