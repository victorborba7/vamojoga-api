from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# --- Request ---
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    full_name: str | None = Field(default=None, max_length=100)
    invite_token: str | None = None


class UserLogin(BaseModel):
    identifier: str  # e-mail ou username
    password: str


# --- Response ---
class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: str | None
    is_active: bool
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=100)


class VerifyEmailRequest(BaseModel):
    token: str


class GuestInviteValidationResponse(BaseModel):
    guest_name: str
    email: EmailStr
    expires_at: datetime
    is_valid: bool = True

