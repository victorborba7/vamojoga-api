import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


VALID_ACHIEVEMENT_TYPES = ("global", "game")


class Achievement(SQLModel, table=True):
    __tablename__ = "achievements"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=200, unique=True)
    description: str | None = Field(default=None, max_length=500)
    icon_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    type: str = Field(max_length=20)  # 'global' or 'game'
    game_id: uuid.UUID | None = Field(default=None, foreign_key="games.id", index=True)
    criteria_key: str = Field(max_length=100)  # e.g. 'matches_played', 'wins', 'unique_games', 'friends'
    criteria_value: int = Field(default=1)  # threshold to unlock
    points: int = Field(default=10)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)


class UserAchievement(SQLModel, table=True):
    __tablename__ = "user_achievements"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    achievement_id: uuid.UUID = Field(foreign_key="achievements.id", index=True)
    match_id: uuid.UUID | None = Field(default=None, foreign_key="matches.id")
    unlocked_at: datetime = Field(default_factory=_utcnow)
