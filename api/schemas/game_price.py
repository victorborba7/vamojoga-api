from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GamePriceResponse(BaseModel):
    id: UUID
    game_id: UUID
    source_name: str
    price: float
    currency: str
    url: str | None
    scraped_at: datetime

    model_config = {"from_attributes": True}


class PriceHistoryResponse(BaseModel):
    game_id: UUID
    game_name: str
    prices: list[GamePriceResponse]
