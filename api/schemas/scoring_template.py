from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Field types ----
VALID_FIELD_TYPES = ("numeric", "ranking", "boolean")
VALID_MATCH_MODES = ("individual", "team")


# ---- Request ----
class ScoringTemplateFieldCreate(BaseModel):
    name: str = Field(max_length=200)
    field_type: str = Field(max_length=20)
    min_value: int | None = None
    max_value: int | None = None
    display_order: int = 0
    is_required: bool = True
    is_tiebreaker: bool = False


class ScoringTemplateCreate(BaseModel):
    game_id: UUID
    name: str = Field(max_length=200)
    description: str | None = None
    match_mode: str = "individual"
    fields: list[ScoringTemplateFieldCreate] = Field(min_length=1)


class ScoringTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    match_mode: str | None = None
    is_active: bool | None = None
    fields: list[ScoringTemplateFieldCreate] | None = None


# ---- Score entry (used when creating a match) ----
class TemplateScoreEntry(BaseModel):
    template_field_id: UUID
    numeric_value: int | None = None
    boolean_value: bool | None = None
    ranking_value: int | None = None


class PlayerTemplateScores(BaseModel):
    user_id: UUID
    scores: list[TemplateScoreEntry]


# ---- Response ----
class ScoringTemplateFieldResponse(BaseModel):
    id: UUID
    name: str
    field_type: str
    min_value: int | None
    max_value: int | None
    display_order: int
    is_required: bool
    is_tiebreaker: bool = False

    model_config = {"from_attributes": True}


class ScoringTemplateResponse(BaseModel):
    id: UUID
    game_id: UUID
    game_name: str | None = None
    created_by: UUID
    created_by_username: str | None = None
    name: str
    description: str | None
    match_mode: str = "individual"
    is_active: bool
    fields: list[ScoringTemplateFieldResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScoringTemplateListResponse(BaseModel):
    id: UUID
    game_id: UUID
    game_name: str | None = None
    created_by: UUID
    created_by_username: str | None = None
    name: str
    description: str | None
    match_mode: str = "individual"
    is_active: bool
    field_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Match template score response ----
class MatchTemplateScoreResponse(BaseModel):
    template_field_id: UUID
    field_name: str | None = None
    field_type: str | None = None
    numeric_value: int | None
    boolean_value: bool | None
    ranking_value: int | None

    model_config = {"from_attributes": True}
