import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PushSubscription(SQLModel, table=True):
    __tablename__ = "push_subscriptions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    endpoint: str = Field(max_length=2048, unique=True, sa_column_kwargs={"unique": True})
    p256dh: str = Field(max_length=512)
    auth: str = Field(max_length=256)
    created_at: datetime = Field(default_factory=_utcnow)
