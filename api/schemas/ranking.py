from uuid import UUID

from pydantic import BaseModel


class RankingEntry(BaseModel):
    user_id: UUID
    username: str
    total_matches: int
    total_wins: int
    win_rate: float

    model_config = {"from_attributes": True}


class UserStats(BaseModel):
    user_id: UUID
    username: str
    total_matches: int
    total_wins: int
    win_rate: float
    matches_by_game: list["GameStats"] = []

    model_config = {"from_attributes": True}


class GameStats(BaseModel):
    game_id: UUID
    game_name: str
    total_matches: int
    total_wins: int
    win_rate: float

    model_config = {"from_attributes": True}
