import re
import uuid
from uuid import UUID

from sqlalchemy import case, func, literal, nullslast, or_, select
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
        biblioteca e favoritos do usuário, excluindo jogos que ele já possui.
        Mecânicas de jogos favoritados têm peso 2x na pontuação.

        Usa CTEs e GROUP BY em vez de subqueries correlacionadas para evitar
        N scans em game_mechanics (um por jogo candidato).
        """
        from api.models.user_game_library import UserGameLibrary
        from api.models.user_game_favorite import UserGameFavorite
        from api.models.mechanic import GameMechanic
        from sqlalchemy import Integer

        # CTE: IDs dos jogos que o usuário já tem
        owned_cte = (
            select(UserGameLibrary.game_id)
            .where(UserGameLibrary.user_id == user_id)
            .cte("owned")
        )

        # CTE: mechanic_ids dos jogos da biblioteca
        lib_mech_cte = (
            select(GameMechanic.mechanic_id.distinct())
            .where(GameMechanic.game_id.in_(select(owned_cte.c.game_id)))
            .cte("lib_mechs")
        )

        # CTE: mechanic_ids dos jogos favoritos
        fav_mech_cte = (
            select(GameMechanic.mechanic_id.distinct())
            .join(UserGameFavorite, UserGameFavorite.game_id == GameMechanic.game_id)
            .where(UserGameFavorite.user_id == user_id)
            .cte("fav_mechs")
        )

        # CTE: para cada jogo candidato, conta overlaps com biblioteca e favoritos
        # Filtra na fonte: só entra game_mechanics de mecânicas que o usuário conhece.
        lib_match = func.count(
            case((GameMechanic.mechanic_id.in_(select(lib_mech_cte.c.mechanic_id)), literal(1)), else_=None)
        )
        fav_match = func.count(
            case((GameMechanic.mechanic_id.in_(select(fav_mech_cte.c.mechanic_id)), literal(1)), else_=None)
        )

        scores_cte = (
            select(
                GameMechanic.game_id,
                lib_match.label("lib_score"),
                fav_match.label("fav_score"),
            )
            .where(
                GameMechanic.mechanic_id.in_(select(lib_mech_cte.c.mechanic_id)),
                GameMechanic.game_id.not_in(select(owned_cte.c.game_id)),
            )
            .group_by(GameMechanic.game_id)
            .cte("scores")
        )

        score_expr = (
            scores_cte.c.lib_score.cast(Integer) + scores_cte.c.fav_score.cast(Integer) * 2
        )

        statement = (
            select(Game)
            .join(scores_cte, scores_cte.c.game_id == Game.id)
            .where(Game.is_active == True)  # noqa: E712
            .order_by(
                score_expr.desc(),
                nullslast(Game.bayes_rating.desc()),
                nullslast(Game.rank),
            )
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
