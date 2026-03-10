import uuid

from sqlmodel import Field, SQLModel


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, max_length=200)


class GameCategory(SQLModel, table=True):
    __tablename__ = "game_categories"

    game_id: uuid.UUID = Field(foreign_key="games.id", primary_key=True)
    category_id: int = Field(foreign_key="categories.id", primary_key=True)
