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
    rank: int | None = None
    bayes_rating: float | None = None
    avg_rating: float | None = None
    users_rated: int | None = None
    subtitle: str | None = None
    year: int | None = None
    best_players: str | None = None
    min_play_time: int | None = None
    max_play_time: int | None = None
    min_age: int | None = None
    weight: float | None = None
    game_type: str | None = None
    is_expansion: bool = False


class GameUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    image_url: str | None = None
    min_players: int | None = None
    max_players: int | None = None
    # BGG metadata (optional)
    bgg_id: int | None = None
    rank: int | None = None
    bayes_rating: float | None = None
    avg_rating: float | None = None
    users_rated: int | None = None
    subtitle: str | None = None
    year: int | None = None
    best_players: str | None = None
    min_play_time: int | None = None
    max_play_time: int | None = None
    min_age: int | None = None
    weight: float | None = None
    game_type: str | None = None
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
    rank: int | None
    bayes_rating: float | None
    avg_rating: float | None
    users_rated: int | None
    subtitle: str | None
    year: int | None
    best_players: str | None
    min_play_time: int | None
    max_play_time: int | None
    min_age: int | None
    weight: float | None
    game_type: str | None
    is_expansion: bool
    thumbnail_url: str | None = None
    playing_time: int | None = None
    last_bgg_sync_at: datetime | None = None
    # Star schema entities (populated on detail endpoint)
    mechanics: list[str] = []
    categories: list[str] = []
    designers: list[str] = []
    publishers: list[str] = []

    model_config = {"from_attributes": True}
