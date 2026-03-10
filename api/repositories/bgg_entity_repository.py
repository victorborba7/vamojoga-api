import uuid
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.mechanic import Mechanic, GameMechanic
from api.models.category import Category, GameCategory
from api.models.designer import Designer, GameDesigner
from api.models.publisher import Publisher, GamePublisher


class BggEntityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Single-game save (used by sync_game_by_bgg_id for individual sync)
    # ------------------------------------------------------------------

    async def save_game_entities(
        self,
        game_id: uuid.UUID,
        mechanics: list[str],
        categories: list[str],
        designers: list[str],
        publishers: list[str],
    ) -> None:
        await self.save_batch_entities([
            (game_id, mechanics, categories, designers, publishers)
        ])

    # ------------------------------------------------------------------
    # Batch save — processes all games in minimal SQL round-trips
    # ------------------------------------------------------------------

    async def save_batch_entities(
        self,
        items: Sequence[tuple[uuid.UUID, list[str], list[str], list[str], list[str]]],
    ) -> None:
        """
        Replaces BGG entity associations for multiple games at once.
        Each item is (game_id, mechanics, categories, designers, publishers).
        Uses bulk SQL operations to minimize round-trips to the database.
        """
        if not items:
            return

        game_ids = [item[0] for item in items]

        # items[i][1] = mechanics, [2] = categories, [3] = designers, [4] = publishers
        await self._replace_batch(game_ids, {it[0]: it[1] for it in items}, Mechanic,  GameMechanic,  "mechanic_id")
        await self._replace_batch(game_ids, {it[0]: it[2] for it in items}, Category,  GameCategory,  "category_id")
        await self._replace_batch(game_ids, {it[0]: it[3] for it in items}, Designer,  GameDesigner,  "designer_id")
        await self._replace_batch(game_ids, {it[0]: it[4] for it in items}, Publisher, GamePublisher, "publisher_id")

    async def _replace_batch(
        self,
        game_ids: list[uuid.UUID],
        game_names_map: dict[uuid.UUID, list[str]],
        LookupModel,
        JunctionModel,
        fk_col: str,
    ) -> None:
        # 1. Delete all junction rows for ALL games at once
        await self.session.execute(
            delete(JunctionModel).where(JunctionModel.game_id.in_(game_ids))
        )

        # 2. Collect unique names across all games
        all_names: set[str] = set()
        for names in game_names_map.values():
            all_names.update(n.strip() for n in names if n.strip())

        if not all_names:
            return

        # 3. Bulk upsert all lookup rows in one statement
        await self.session.execute(
            insert(LookupModel)
            .values([{"name": n} for n in all_names])
            .on_conflict_do_nothing(index_elements=["name"])
        )

        # 4. Fetch all IDs in one query
        result = await self.session.execute(
            select(LookupModel.id, LookupModel.name)
            .where(LookupModel.name.in_(list(all_names)))
        )
        name_to_id = {row.name: row.id for row in result}

        # 5. Build ALL junction rows for all games at once
        junction_rows = []
        for game_id, names in game_names_map.items():
            for n in names:
                n = n.strip()
                if n and n in name_to_id:
                    junction_rows.append({"game_id": game_id, fk_col: name_to_id[n]})

        if junction_rows:
            await self.session.execute(
                insert(JunctionModel)
                .values(junction_rows)
                .on_conflict_do_nothing()
            )

    # ------------------------------------------------------------------
    # Read helpers (used by game_service for API responses)
    # ------------------------------------------------------------------

    async def get_mechanics(self, game_id: uuid.UUID) -> list[str]:
        return await self._get_names(game_id, Mechanic, GameMechanic, "mechanic_id")

    async def get_categories(self, game_id: uuid.UUID) -> list[str]:
        return await self._get_names(game_id, Category, GameCategory, "category_id")

    async def get_designers(self, game_id: uuid.UUID) -> list[str]:
        return await self._get_names(game_id, Designer, GameDesigner, "designer_id")

    async def get_publishers(self, game_id: uuid.UUID) -> list[str]:
        return await self._get_names(game_id, Publisher, GamePublisher, "publisher_id")

    async def _get_names(self, game_id, LookupModel, JunctionModel, fk_col: str) -> list[str]:
        stmt = (
            select(LookupModel.name)
            .join(JunctionModel, LookupModel.id == getattr(JunctionModel, fk_col))
            .where(JunctionModel.game_id == game_id)
            .order_by(LookupModel.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
