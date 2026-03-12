from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Request ---

class AchievementCreate(BaseModel):
    name: str
    description: str | None = None
    icon_url: str | None = None
    type: str = "global"  # 'global' or 'game'
    game_id: UUID | None = None
    criteria_key: str  # e.g. 'matches_played', 'wins', 'unique_games', 'friends'
    criteria_value: int = 1
    points: int = 10


class AchievementImport(BaseModel):
    achievements: list[AchievementCreate]


# --- Response ---

class AchievementResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    icon_url: str | None
    type: str
    game_id: UUID | None
    criteria_key: str
    criteria_value: int
    points: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserAchievementResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str | None = None
    achievement_id: UUID
    achievement_name: str
    achievement_description: str | None = None
    achievement_icon_url: str | None = None
    achievement_type: str
    achievement_points: int
    match_id: UUID | None
    unlocked_at: datetime

    model_config = {"from_attributes": True}


class NewlyUnlockedAchievement(BaseModel):
    """Returned after match creation to notify of newly unlocked achievements."""
    id: UUID
    name: str
    description: str | None
    icon_url: str | None
    points: int
