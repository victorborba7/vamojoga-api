import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Collection(SQLModel, table=True):
    __tablename__ = "collections"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    owner_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=_utcnow)


class CollectionMembro(SQLModel, table=True):
    __tablename__ = "collection_membros"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    collection_id: uuid.UUID = Field(foreign_key="collections.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    # role: "owner" | "member"
    role: str = Field(default="member", max_length=20)
    joined_at: datetime = Field(default_factory=_utcnow)


class CollectionJogo(SQLModel, table=True):
    __tablename__ = "collection_jogos"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    collection_id: uuid.UUID = Field(foreign_key="collections.id", index=True)
    game_id: uuid.UUID = Field(foreign_key="games.id", index=True)
    added_by: uuid.UUID = Field(foreign_key="users.id")
    added_at: datetime = Field(default_factory=_utcnow)
