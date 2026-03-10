import uuid

from sqlmodel import Field, SQLModel


class Designer(SQLModel, table=True):
    __tablename__ = "designers"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, max_length=200)


class GameDesigner(SQLModel, table=True):
    __tablename__ = "game_designers"

    game_id: uuid.UUID = Field(foreign_key="games.id", primary_key=True)
    designer_id: int = Field(foreign_key="designers.id", primary_key=True)
