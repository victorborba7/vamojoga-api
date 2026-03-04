from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Request ---
class GameCreate(BaseModel):
    name: str
    description: str | None = None
    image_url: str | None = None
    min_players: int = 2
    max_players: int = 10
    # BGG metadata (optional)
    bgg_id: int | None = None
    bgg_rank: int | None = None
    bgg_rating: float | None = None
    bgg_avg_rating: float | None = None
    bgg_users_rated: int | None = None
    subtitle: str | None = None
    year: int | None = None
    best_players: str | None = None
    min_play_time: int | None = None
    max_play_time: int | None = None
    min_age: int | None = None
    weight: float | None = None
    bgg_type: str | None = None
    is_expansion: bool = False


class GameUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    image_url: str | None = None
    min_players: int | None = None
    max_players: int | None = None
    # BGG metadata (optional)
    bgg_id: int | None = None
    bgg_rank: int | None = None
    bgg_rating: float | None = None
    bgg_avg_rating: float | None = None
    bgg_users_rated: int | None = None
    subtitle: str | None = None
    year: int | None = None
    best_players: str | None = None
    min_play_time: int | None = None
    max_play_time: int | None = None
    min_age: int | None = None
    weight: float | None = None
    bgg_type: str | None = None
    is_expansion: bool | None = None


# --- Response ---
class GameResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    image_url: str | None
    min_players: int
    max_players: int
    is_active: bool
    created_at: datetime
    # BGG metadata
    bgg_id: int | None
    bgg_rank: int | None
    bgg_rating: float | None
    bgg_avg_rating: float | None
    bgg_users_rated: int | None
    subtitle: str | None
    year: int | None
    best_players: str | None
    min_play_time: int | None
    max_play_time: int | None
    min_age: int | None
    weight: float | None
    bgg_type: str | None
    is_expansion: bool

    model_config = {"from_attributes": True}
