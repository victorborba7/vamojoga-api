import uuid

from sqlmodel import Field, SQLModel


class Publisher(SQLModel, table=True):
    __tablename__ = "publishers"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, max_length=200)


class GamePublisher(SQLModel, table=True):
    __tablename__ = "game_publishers"

    game_id: uuid.UUID = Field(foreign_key="games.id", primary_key=True)
    publisher_id: int = Field(foreign_key="publishers.id", primary_key=True)
