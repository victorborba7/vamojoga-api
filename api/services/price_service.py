from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories.game_repository import GameRepository
from api.repositories.price_repository import PriceRepository
from api.schemas.game_price import GamePriceResponse, PriceHistoryResponse


class PriceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.price_repo = PriceRepository(session)
        self.game_repo = GameRepository(session)

    async def _validate_game(self, game_id: UUID) -> str:
        """Validate game exists and return its name."""
        game = await self.game_repo.get_by_id(game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jogo não encontrado",
            )
        return game.name

    async def get_price_history(
        self,
        game_id: UUID,
        source: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> PriceHistoryResponse:
        game_name = await self._validate_game(game_id)
        rows = await self.price_repo.get_price_history(
            game_id, source=source, date_from=date_from, date_to=date_to
        )
        prices = [GamePriceResponse(**r) for r in rows]
        return PriceHistoryResponse(game_id=game_id, game_name=game_name, prices=prices)

    async def get_latest_prices(self, game_id: UUID) -> list[GamePriceResponse]:
        await self._validate_game(game_id)
        rows = await self.price_repo.get_latest_prices(game_id)
        return [GamePriceResponse(**r) for r in rows]
