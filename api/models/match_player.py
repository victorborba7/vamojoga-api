import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MatchPlayer(SQLModel, table=True):
    __tablename__ = "match_players"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    match_id: uuid.UUID = Field(foreign_key="matches.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    position: int = Field(ge=1)
    score: int = Field(default=0)
    is_winner: bool = Field(default=False)
    scores_submitted: bool = Field(default=False)
    scores_submitted_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
