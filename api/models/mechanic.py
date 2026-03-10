import uuid

from sqlmodel import Field, SQLModel


class Mechanic(SQLModel, table=True):
    __tablename__ = "mechanics"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, max_length=200)


class GameMechanic(SQLModel, table=True):
    __tablename__ = "game_mechanics"

    game_id: uuid.UUID = Field(foreign_key="games.id", primary_key=True)
    mechanic_id: int = Field(foreign_key="mechanics.id", primary_key=True)
