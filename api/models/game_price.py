import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Numeric, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PriceSource(SQLModel, table=True):
    __tablename__ = "price_sources"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100, unique=True)
    base_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)


class GamePrice(SQLModel, table=True):
    __tablename__ = "game_prices"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    game_id: uuid.UUID = Field(foreign_key="games.id", index=True)
    source_id: uuid.UUID = Field(foreign_key="price_sources.id", index=True)
    price: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    currency: str = Field(default="BRL", max_length=3)
    url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    scraped_at: datetime = Field(default_factory=_utcnow)
