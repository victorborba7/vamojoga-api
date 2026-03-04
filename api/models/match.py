import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Match(SQLModel, table=True):
    __tablename__ = "matches"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    game_id: uuid.UUID = Field(foreign_key="games.id", index=True)
    created_by: uuid.UUID = Field(foreign_key="users.id")
    played_at: datetime = Field(default_factory=_utcnow)
    notes: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=_utcnow)
