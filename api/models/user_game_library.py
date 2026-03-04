import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserGameLibrary(SQLModel, table=True):
    __tablename__ = "user_game_library"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    game_id: uuid.UUID = Field(foreign_key="games.id", index=True)
    created_at: datetime = Field(default_factory=_utcnow)
