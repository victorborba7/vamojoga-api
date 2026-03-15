from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class GuestCreate(BaseModel):
    name: str
    email: EmailStr | None = None


class GuestUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None


class GuestResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    email: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
