import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Game(SQLModel, table=True):
    __tablename__ = "games"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True, max_length=500)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    image_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    min_players: int = Field(default=2)
    max_players: int = Field(default=10)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)

    # BGG (BoardGameGeek) metadata
    bgg_id: int | None = Field(default=None, index=True, unique=True)
    rank: int | None = Field(default=None)
    bayes_rating: float | None = Field(default=None)     # bayesaverage (weighted)
    avg_rating: float | None = Field(default=None)       # average (raw)
    users_rated: int | None = Field(default=None)
    subtitle: str | None = Field(default=None, max_length=500)
    year: int | None = Field(default=None)
    best_players: str | None = Field(default=None, max_length=50)
    min_play_time: int | None = Field(default=None)
    max_play_time: int | None = Field(default=None)
    min_age: int | None = Field(default=None)
    weight: float | None = Field(default=None)
    game_type: str | None = Field(default=None, max_length=100)
    is_expansion: bool = Field(default=False)

    # BGG enrichment fields (populated by sync pipeline)
    thumbnail_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    playing_time: int | None = Field(default=None)
    last_bgg_sync_at: datetime | None = Field(default=None)
    # mechanics, categories, designers, publishers → see models/bgg_entities.py (star schema)

    # Ludopedia enrichment (Portuguese localization, populated by sync-ludopedia pipeline)
    name_pt: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    description_pt: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ludopedia_id: int | None = Field(default=None)
    ludopedia_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    last_ludopedia_sync_at: datetime | None = Field(default=None)

    # Expansão → jogo base
    # parent_bgg_id: bgg_id do jogo pai (populado durante o sync BGG)
    # parent_game_id: UUID resolvido do jogo pai (preenchido se o pai já existe no banco)
    parent_bgg_id: int | None = Field(default=None)
    parent_game_id: uuid.UUID | None = Field(default=None, foreign_key="games.id", nullable=True)
