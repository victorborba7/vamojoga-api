import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


VALID_MATCH_MODES = ("individual", "team")


class ScoringTemplate(SQLModel, table=True):
    __tablename__ = "scoring_templates"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    game_id: uuid.UUID = Field(foreign_key="games.id", index=True)
    created_by: uuid.UUID = Field(foreign_key="users.id", index=True)
    name: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=500)
    match_mode: str = Field(default="individual", max_length=20)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ScoringTemplateField(SQLModel, table=True):
    __tablename__ = "scoring_template_fields"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    template_id: uuid.UUID = Field(foreign_key="scoring_templates.id", index=True)
    name: str = Field(max_length=200)
    field_type: str = Field(max_length=20)  # 'numeric', 'ranking', 'boolean'
    min_value: int | None = Field(default=None)
    max_value: int | None = Field(default=None)
    display_order: int = Field(default=0)
    is_required: bool = Field(default=True)
    is_tiebreaker: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)


class MatchTemplateScore(SQLModel, table=True):
    __tablename__ = "match_template_scores"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    match_player_id: uuid.UUID = Field(foreign_key="match_players.id", index=True)
    template_field_id: uuid.UUID = Field(foreign_key="scoring_template_fields.id", index=True)
    numeric_value: int | None = Field(default=None)
    boolean_value: bool | None = Field(default=None)
    ranking_value: int | None = Field(default=None)
