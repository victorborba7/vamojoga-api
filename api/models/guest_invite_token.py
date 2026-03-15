import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class GuestInviteToken(SQLModel, table=True):
    __tablename__ = "guest_invite_tokens"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    guest_id: uuid.UUID = Field(foreign_key="guests.id", index=True)
    email: str = Field(max_length=255, index=True)
    token: str = Field(index=True, unique=True, max_length=255)
    expires_at: datetime
    used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)
