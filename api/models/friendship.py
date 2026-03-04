import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Friendship(SQLModel, table=True):
    __tablename__ = "friendships"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    requester_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    addressee_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    status: str = Field(default="pending", max_length=20)  # pending, accepted, rejected
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
