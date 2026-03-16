import re
import uuid
from uuid import UUID

from sqlalchemy import case, func, nullslast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.game import Game


def _normalize(text: str) -> str:
    """Remove pontuação e espaços duplos para busca tolerante (ex: 'ticket to ride europe')."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)).strip()


class GameRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, game: Game) -> Game:
        self.session.add(game)
        await self.session.commit()
        await self.session.refresh(game)
        return game

    async def get_by_id(self, game_id: UUID) -> Game | None:
        statement = select(Game).where(Game.id == game_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Game | None:
        statement = select(Game).where(Game.name == name)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_bgg_id(self, bgg_id: int) -> Game | None:
        statement = select(Game).where(Game.bgg_id == bgg_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Game]:
        statement = select(Game).where(Game.is_active == True).offset(skip).limit(limit)  # noqa: E712
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_pending_bgg_sync(
        self,
        force: bool = False,
        limit: int | None = None,
    ) -> list[Game]:
        """
        Returns games that have bgg_id set but are missing BGG enrichment data.
        If force=True, returns all games with bgg_id regardless of sync status.
        Ordered by rank ascending (most popular first), NULLs last.
        """
        statement = select(Game).where(Game.bgg_id.is_not(None))
        if not force:
            statement = statement.where(
                or_(
                    Game.image_url.is_(None),
                    Game.last_bgg_sync_at.is_(None),
                )
            )
        statement = statement.order_by(nullslast(Game.rank))
        if limit is not None:
            statement = statement.limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def search_by_name(self, query: str, limit: int = 20, exclude_expansions: bool = False) -> list[Game]:
        # Versão normalizada da query (sem pontuação) para tolerar "ticket to ride europe"
        # bater com "Ticket to Ride: Europe"
        clean_query = _normalize(query)

        # Nome do jogo normalizado no banco via regexp_replace postgres
        normalized_name = func.regexp_replace(Game.name, r"[^\w\s]", " ", "g")
        normalized_name_pt = func.regexp_replace(Game.name_pt, r"[^\w\s]", " ", "g")

        filters = [
            Game.is_active == True,  # noqa: E712
            or_(
                Game.name.ilike(f"%{query}%"),
                normalized_name.ilike(f"%{clean_query}%"),
                Game.name_pt.ilike(f"%{query}%"),
                normalized_name_pt.ilike(f"%{clean_query}%"),
            ),
        ]
        if exclude_expansions:
            filters.append(Game.is_expansion == False)  # noqa: E712

        statement = (
            select(Game)
            .where(*filters)
            .order_by(
                # 1. Jogos base antes de expansões
                case((Game.is_expansion == False, 0), else_=1),  # noqa: E712
                # 2. Nomes que começam com a query antes de matches no meio
                case(
                    (
                        or_(
                            Game.name.ilike(f"{query}%"),
                            normalized_name.ilike(f"{clean_query}%"),
                            Game.name_pt.ilike(f"{query}%"),
                            normalized_name_pt.ilike(f"{clean_query}%"),
                        ),
                        0,
                    ),
                    else_=1,
                ),
                # 3. Mais populares primeiro (rank menor = mais popular); NULLs por último
                nullslast(Game.rank),
                # 4. Alfabético como desempate final
                Game.name,
            )
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update(self, game: Game) -> Game:
        self.session.add(game)
        await self.session.commit()
        await self.session.refresh(game)
        return game

    async def get_recommendations(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> list[Game]:
        """
        Retorna jogos recomendados baseados nas mecânicas dos jogos da
        biblioteca do usuário, excluindo jogos que ele já possui.
        Ordenados por número de mecânicas em comum (desc) e depois por rating.
        """
        from api.models.user_game_library import UserGameLibrary
        from api.models.mechanic import GameMechanic
        from sqlalchemy import distinct, Integer

        # Subquery: IDs dos jogos que o usuário já tem
        owned_subq = (
            select(UserGameLibrary.game_id)
            .where(UserGameLibrary.user_id == user_id)
            .scalar_subquery()
        )

        # Subquery: mechanic_ids dos jogos que o usuário tem
        user_mechanic_subq = (
            select(distinct(GameMechanic.mechanic_id))
            .where(GameMechanic.game_id.in_(owned_subq))
            .scalar_subquery()
        )

        # Conta quantas mecânicas em comum cada jogo candidato tem
        overlap_count = (
            select(func.count())
            .where(
                GameMechanic.game_id == Game.id,
                GameMechanic.mechanic_id.in_(user_mechanic_subq),
            )
            .correlate(Game)
            .scalar_subquery()
        )

        statement = (
            select(Game)
            .where(
                Game.is_active == True,  # noqa: E712
                Game.id.not_in(owned_subq),
                overlap_count > 0,
            )
            .order_by(
                overlap_count.cast(Integer).desc(),
                nullslast(Game.bayes_rating.desc()),
                nullslast(Game.rank),
            )
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
