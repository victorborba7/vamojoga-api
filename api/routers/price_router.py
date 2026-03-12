from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.game_price import GamePriceResponse, PriceHistoryResponse
from api.services.price_service import PriceService

router = APIRouter(prefix="/games", tags=["Prices"])


@router.get("/{game_id}/prices", response_model=PriceHistoryResponse)
async def get_price_history(
    game_id: UUID,
    source: str | None = Query(None, description="Filter by source name"),
    date_from: datetime | None = Query(None, description="Start date filter"),
    date_to: datetime | None = Query(None, description="End date filter"),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> PriceHistoryResponse:
    service = PriceService(session)
    return await service.get_price_history(
        game_id, source=source, date_from=date_from, date_to=date_to
    )


@router.get("/{game_id}/prices/latest", response_model=list[GamePriceResponse])
async def get_latest_prices(
    game_id: UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> list[GamePriceResponse]:
    service = PriceService(session)
    return await service.get_latest_prices(game_id)
