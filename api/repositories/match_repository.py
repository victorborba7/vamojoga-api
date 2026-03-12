from uuid import UUID

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.game import Game
from api.models.match import Match
from api.models.match_player import MatchPlayer
from api.models.scoring_template import ScoringTemplate
from api.models.user import User


class MatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_match(self, match: Match) -> Match:
        self.session.add(match)
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def create_match_players(self, players: list[MatchPlayer]) -> list[MatchPlayer]:
        for player in players:
            self.session.add(player)
        await self.session.commit()
        for player in players:
            await self.session.refresh(player)
        return players

    async def get_match_by_id(self, match_id: UUID) -> Match | None:
        statement = select(Match).where(Match.id == match_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_match_players(self, match_id: UUID) -> list[MatchPlayer]:
        statement = (
            select(MatchPlayer)
            .where(MatchPlayer.match_id == match_id)
            .order_by(MatchPlayer.position)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_match_players_with_username(self, match_id: UUID) -> list[dict]:
        """Get match players with username in a single query."""
        statement = (
            select(
                MatchPlayer.id,
                MatchPlayer.user_id,
                User.username,
                MatchPlayer.position,
                MatchPlayer.score,
                MatchPlayer.is_winner,
            )
            .join(User, User.id == MatchPlayer.user_id)
            .where(MatchPlayer.match_id == match_id)
            .order_by(MatchPlayer.position)
        )
        result = await self.session.execute(statement)
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "username": row.username,
                "position": row.position,
                "score": row.score,
                "is_winner": row.is_winner,
            }
            for row in result.all()
        ]

    async def get_match_with_details(self, match_id: UUID) -> dict | None:
        """Get a single match with game name in one query."""
        statement = (
            select(
                Match.id,
                Match.game_id,
                Game.name.label("game_name"),
                Game.image_url.label("game_image_url"),
                Match.created_by,
                Match.played_at,
                Match.notes,
                Match.match_mode,
                Match.scoring_template_id,
                ScoringTemplate.name.label("scoring_template_name"),
                Match.created_at,
            )
            .join(Game, Game.id == Match.game_id)
            .outerjoin(ScoringTemplate, ScoringTemplate.id == Match.scoring_template_id)
            .where(Match.id == match_id)
        )
        result = await self.session.execute(statement)
        row = result.one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "game_id": row.game_id,
            "game_name": row.game_name,
            "game_image_url": row.game_image_url,
            "created_by": row.created_by,
            "played_at": row.played_at,
            "notes": row.notes,
            "match_mode": row.match_mode,
            "scoring_template_id": row.scoring_template_id,
            "scoring_template_name": row.scoring_template_name,
            "created_at": row.created_at,
        }

    async def get_user_matches_with_details(
        self, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[dict]:
        """Get user matches with game names and all players+usernames efficiently."""
        # Step 1: Get match IDs for the user
        match_ids_stmt = (
            select(Match.id)
            .join(MatchPlayer, MatchPlayer.match_id == Match.id)
            .where(MatchPlayer.user_id == user_id)
            .order_by(Match.played_at.desc())
            .offset(skip)
            .limit(limit)
        )
        match_ids_result = await self.session.execute(match_ids_stmt)
        match_ids = [row[0] for row in match_ids_result.all()]

        if not match_ids:
            return []

        # Step 2: Get matches with game name
        matches_stmt = (
            select(
                Match.id,
                Match.game_id,
                Game.name.label("game_name"),
                Game.image_url.label("game_image_url"),
                Match.created_by,
                Match.played_at,
                Match.notes,
                Match.match_mode,
                Match.scoring_template_id,
                ScoringTemplate.name.label("scoring_template_name"),
                Match.created_at,
            )
            .join(Game, Game.id == Match.game_id)
            .outerjoin(ScoringTemplate, ScoringTemplate.id == Match.scoring_template_id)
            .where(Match.id.in_(match_ids))
            .order_by(Match.played_at.desc())
        )
        matches_result = await self.session.execute(matches_stmt)
        matches = matches_result.all()

        # Step 3: Get all players for all matches in one query
        players_stmt = (
            select(
                MatchPlayer.id,
                MatchPlayer.match_id,
                MatchPlayer.user_id,
                User.username,
                MatchPlayer.position,
                MatchPlayer.score,
                MatchPlayer.is_winner,
            )
            .join(User, User.id == MatchPlayer.user_id)
            .where(MatchPlayer.match_id.in_(match_ids))
            .order_by(MatchPlayer.position)
        )
        players_result = await self.session.execute(players_stmt)
        all_players = players_result.all()

        # Group players by match_id
        players_by_match: dict[UUID, list[dict]] = {}
        for p in all_players:
            players_by_match.setdefault(p.match_id, []).append({
                "id": p.id,
                "user_id": p.user_id,
                "username": p.username,
                "position": p.position,
                "score": p.score,
                "is_winner": p.is_winner,
            })

        # Build result
        result = []
        for m in matches:
            result.append({
                "id": m.id,
                "game_id": m.game_id,
                "game_name": m.game_name,
                "game_image_url": m.game_image_url,
                "created_by": m.created_by,
                "played_at": m.played_at,
                "notes": m.notes,
                "match_mode": m.match_mode,
                "scoring_template_id": m.scoring_template_id,
                "scoring_template_name": m.scoring_template_name,
                "created_at": m.created_at,
                "players": players_by_match.get(m.id, []),
            })
        return result

    async def get_matches_by_user(
        self, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[Match]:
        statement = (
            select(Match)
            .join(MatchPlayer, MatchPlayer.match_id == Match.id)
            .where(MatchPlayer.user_id == user_id)
            .order_by(Match.played_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_global_ranking(
        self, limit: int = 50, user_ids: list[UUID] | None = None
    ) -> list[dict]:
        wins_expr = func.sum(cast(MatchPlayer.is_winner, Integer))
        statement = (
            select(
                MatchPlayer.user_id,
                User.username,
                func.count(MatchPlayer.id).label("total_matches"),
                wins_expr.label("total_wins"),
            )
            .join(User, User.id == MatchPlayer.user_id)
            .group_by(MatchPlayer.user_id, User.username)
            .order_by(wins_expr.desc())
            .limit(limit)
        )
        if user_ids is not None:
            statement = statement.where(MatchPlayer.user_id.in_(user_ids))
        result = await self.session.execute(statement)
        rows = result.all()
        return [
            {
                "user_id": row.user_id,
                "username": row.username,
                "total_matches": row.total_matches,
                "total_wins": row.total_wins or 0,
            }
            for row in rows
        ]

    async def get_ranking_by_game(
        self, game_id: UUID, limit: int = 50, user_ids: list[UUID] | None = None
    ) -> list[dict]:
        wins_expr = func.sum(cast(MatchPlayer.is_winner, Integer))
        statement = (
            select(
                MatchPlayer.user_id,
                User.username,
                func.count(MatchPlayer.id).label("total_matches"),
                wins_expr.label("total_wins"),
            )
            .join(Match, Match.id == MatchPlayer.match_id)
            .join(User, User.id == MatchPlayer.user_id)
            .where(Match.game_id == game_id)
            .group_by(MatchPlayer.user_id, User.username)
            .order_by(wins_expr.desc())
            .limit(limit)
        )
        if user_ids is not None:
            statement = statement.where(MatchPlayer.user_id.in_(user_ids))
        result = await self.session.execute(statement)
        rows = result.all()
        return [
            {
                "user_id": row.user_id,
                "username": row.username,
                "total_matches": row.total_matches,
                "total_wins": row.total_wins or 0,
            }
            for row in rows
        ]

    async def get_user_stats(self, user_id: UUID) -> list[dict]:
        statement = (
            select(
                Match.game_id,
                Game.name.label("game_name"),
                func.count(MatchPlayer.id).label("total_matches"),
                func.sum(cast(MatchPlayer.is_winner, Integer)).label("total_wins"),
            )
            .join(Match, Match.id == MatchPlayer.match_id)
            .join(Game, Game.id == Match.game_id)
            .where(MatchPlayer.user_id == user_id)
            .group_by(Match.game_id, Game.name)
        )
        result = await self.session.execute(statement)
        rows = result.all()
        return [
            {
                "game_id": row.game_id,
                "game_name": row.game_name,
                "total_matches": row.total_matches,
                "total_wins": row.total_wins or 0,
            }
            for row in rows
        ]
