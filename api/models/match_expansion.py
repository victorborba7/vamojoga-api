import uuid

from sqlmodel import Field, SQLModel


class MatchExpansion(SQLModel, table=True):
    __tablename__ = "match_expansions"

    match_id: uuid.UUID = Field(foreign_key="matches.id", primary_key=True)
    game_id: uuid.UUID = Field(foreign_key="games.id", primary_key=True)
