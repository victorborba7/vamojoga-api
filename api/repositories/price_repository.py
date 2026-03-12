from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.game_price import GamePrice, PriceSource


class PriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_price_history(
        self,
        game_id: UUID,
        source: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        """Get price history for a game, optionally filtered by source and date range."""
        stmt = (
            select(
                GamePrice.id,
                GamePrice.game_id,
                PriceSource.name.label("source_name"),
                GamePrice.price,
                GamePrice.currency,
                GamePrice.url,
                GamePrice.scraped_at,
            )
            .join(PriceSource, PriceSource.id == GamePrice.source_id)
            .where(GamePrice.game_id == game_id)
        )

        if source:
            stmt = stmt.where(PriceSource.name == source)
        if date_from:
            stmt = stmt.where(GamePrice.scraped_at >= date_from)
        if date_to:
            stmt = stmt.where(GamePrice.scraped_at <= date_to)

        stmt = stmt.order_by(GamePrice.scraped_at.asc())

        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get_latest_prices(self, game_id: UUID) -> list[dict]:
        """Get the most recent price per source for a game."""
        # Subquery: max scraped_at per source for this game
        from sqlalchemy import func

        subq = (
            select(
                GamePrice.source_id,
                func.max(GamePrice.scraped_at).label("max_scraped_at"),
            )
            .where(GamePrice.game_id == game_id)
            .group_by(GamePrice.source_id)
            .subquery()
        )

        stmt = (
            select(
                GamePrice.id,
                GamePrice.game_id,
                PriceSource.name.label("source_name"),
                GamePrice.price,
                GamePrice.currency,
                GamePrice.url,
                GamePrice.scraped_at,
            )
            .join(PriceSource, PriceSource.id == GamePrice.source_id)
            .join(
                subq,
                (GamePrice.source_id == subq.c.source_id)
                & (GamePrice.scraped_at == subq.c.max_scraped_at),
            )
            .where(GamePrice.game_id == game_id)
            .order_by(PriceSource.name)
        )

        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]
