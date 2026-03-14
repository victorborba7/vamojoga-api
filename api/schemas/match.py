from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from api.schemas.scoring_template import MatchTemplateScoreResponse, TemplateScoreEntry
from api.schemas.achievement import NewlyUnlockedAchievement


# --- Request ---
class MatchPlayerCreate(BaseModel):
    user_id: UUID
    position: int = 0
    score: int = 0
    is_winner: bool = False
    template_scores: list[TemplateScoreEntry] = []


class MatchCreate(BaseModel):
    game_id: UUID
    played_at: datetime | None = None
    notes: str | None = None
    scoring_template_id: UUID | None = None
    match_mode: str = "individual"
    collaborative_scoring: bool = False
    players: list[MatchPlayerCreate] = Field(min_length=1)


class PlayerScoreSubmit(BaseModel):
    template_scores: list[TemplateScoreEntry] = []


# --- Response ---
class MatchPlayerResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str | None = None
    position: int
    score: int
    is_winner: bool
    scores_submitted: bool = False
    scores_submitted_at: datetime | None = None
    template_scores: list[MatchTemplateScoreResponse] = []

    model_config = {"from_attributes": True}


class MatchResponse(BaseModel):
    id: UUID
    game_id: UUID
    game_name: str | None = None
    game_image_url: str | None = None
    created_by: UUID
    played_at: datetime
    notes: str | None
    match_mode: str = "individual"
    status: str = "completed"
    scoring_template_id: UUID | None = None
    scoring_template_name: str | None = None
    players: list[MatchPlayerResponse] = []
    unlocked_achievements: list[NewlyUnlockedAchievement] = []
    created_at: datetime

    model_config = {"from_attributes": True}
