from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.game import Game
from api.models.scoring_template import (
    MatchTemplateScore,
    ScoringTemplate,
    ScoringTemplateField,
)
from api.models.user import User


class ScoringTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- Template CRUD ----

    async def create_template(self, template: ScoringTemplate) -> ScoringTemplate:
        self.session.add(template)
        await self.session.commit()
        await self.session.refresh(template)
        return template

    async def create_fields(
        self, fields: list[ScoringTemplateField]
    ) -> list[ScoringTemplateField]:
        self.session.add_all(fields)
        await self.session.commit()
        for field in fields:
            await self.session.refresh(field)
        return fields

    async def get_template_by_id(self, template_id: UUID) -> ScoringTemplate | None:
        stmt = select(ScoringTemplate).where(ScoringTemplate.id == template_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_template_fields(
        self, template_id: UUID
    ) -> list[ScoringTemplateField]:
        stmt = (
            select(ScoringTemplateField)
            .where(ScoringTemplateField.template_id == template_id)
            .order_by(ScoringTemplateField.display_order)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_template_with_details(self, template_id: UUID) -> dict | None:
        stmt = (
            select(
                ScoringTemplate.id,
                ScoringTemplate.game_id,
                Game.name.label("game_name"),
                ScoringTemplate.created_by,
                User.username.label("created_by_username"),
                ScoringTemplate.name,
                ScoringTemplate.description,
                ScoringTemplate.match_mode,
                ScoringTemplate.is_active,
                ScoringTemplate.created_at,
                ScoringTemplate.updated_at,
            )
            .join(Game, Game.id == ScoringTemplate.game_id)
            .join(User, User.id == ScoringTemplate.created_by)
            .where(ScoringTemplate.id == template_id)
        )
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "game_id": row.game_id,
            "game_name": row.game_name,
            "created_by": row.created_by,
            "created_by_username": row.created_by_username,
            "name": row.name,
            "description": row.description,
            "match_mode": row.match_mode,
            "is_active": row.is_active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    async def list_templates_by_game(
        self, game_id: UUID, active_only: bool = True
    ) -> list[dict]:
        stmt = (
            select(
                ScoringTemplate.id,
                ScoringTemplate.game_id,
                Game.name.label("game_name"),
                ScoringTemplate.created_by,
                User.username.label("created_by_username"),
                ScoringTemplate.name,
                ScoringTemplate.description,
                ScoringTemplate.match_mode,
                ScoringTemplate.is_active,
                ScoringTemplate.created_at,
                func.count(ScoringTemplateField.id).label("field_count"),
            )
            .join(Game, Game.id == ScoringTemplate.game_id)
            .join(User, User.id == ScoringTemplate.created_by)
            .outerjoin(
                ScoringTemplateField,
                ScoringTemplateField.template_id == ScoringTemplate.id,
            )
            .where(ScoringTemplate.game_id == game_id)
            .group_by(
                ScoringTemplate.id,
                Game.name,
                User.username,
            )
            .order_by(ScoringTemplate.created_at.desc())
        )
        if active_only:
            stmt = stmt.where(ScoringTemplate.is_active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return [
            {
                "id": row.id,
                "game_id": row.game_id,
                "game_name": row.game_name,
                "created_by": row.created_by,
                "created_by_username": row.created_by_username,
                "name": row.name,
                "description": row.description,
                "match_mode": row.match_mode,
                "is_active": row.is_active,
                "field_count": row.field_count,
                "created_at": row.created_at,
            }
            for row in result.all()
        ]

    async def search_templates(
        self, query: str, limit: int = 20
    ) -> list[dict]:
        stmt = (
            select(
                ScoringTemplate.id,
                ScoringTemplate.game_id,
                Game.name.label("game_name"),
                ScoringTemplate.created_by,
                User.username.label("created_by_username"),
                ScoringTemplate.name,
                ScoringTemplate.description,
                ScoringTemplate.match_mode,
                ScoringTemplate.is_active,
                ScoringTemplate.created_at,
                func.count(ScoringTemplateField.id).label("field_count"),
            )
            .join(Game, Game.id == ScoringTemplate.game_id)
            .join(User, User.id == ScoringTemplate.created_by)
            .outerjoin(
                ScoringTemplateField,
                ScoringTemplateField.template_id == ScoringTemplate.id,
            )
            .where(
                ScoringTemplate.is_active == True,  # noqa: E712
                ScoringTemplate.name.ilike(f"%{query}%"),
            )
            .group_by(
                ScoringTemplate.id,
                Game.name,
                User.username,
            )
            .order_by(ScoringTemplate.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            {
                "id": row.id,
                "game_id": row.game_id,
                "game_name": row.game_name,
                "created_by": row.created_by,
                "created_by_username": row.created_by_username,
                "name": row.name,
                "description": row.description,
                "match_mode": row.match_mode,
                "is_active": row.is_active,
                "field_count": row.field_count,
                "created_at": row.created_at,
            }
            for row in result.all()
        ]

    async def update_template(
        self, template: ScoringTemplate
    ) -> ScoringTemplate:
        self.session.add(template)
        await self.session.commit()
        await self.session.refresh(template)
        return template

    async def delete_fields_by_template(self, template_id: UUID) -> None:
        await self.session.execute(
            delete(ScoringTemplateField)
            .where(ScoringTemplateField.template_id == template_id)
        )
        await self.session.commit()

    # ---- Match template scores ----

    async def create_match_template_scores(
        self, scores: list[MatchTemplateScore]
    ) -> list[MatchTemplateScore]:
        self.session.add_all(scores)
        await self.session.commit()
        for score in scores:
            await self.session.refresh(score)
        return scores

    async def get_match_player_template_scores(
        self, match_player_id: UUID
    ) -> list[dict]:
        stmt = (
            select(
                MatchTemplateScore.template_field_id,
                ScoringTemplateField.name.label("field_name"),
                ScoringTemplateField.field_type,
                MatchTemplateScore.numeric_value,
                MatchTemplateScore.boolean_value,
                MatchTemplateScore.ranking_value,
            )
            .join(
                ScoringTemplateField,
                ScoringTemplateField.id == MatchTemplateScore.template_field_id,
            )
            .where(MatchTemplateScore.match_player_id == match_player_id)
            .order_by(ScoringTemplateField.display_order)
        )
        result = await self.session.execute(stmt)
        return [
            {
                "template_field_id": row.template_field_id,
                "field_name": row.field_name,
                "field_type": row.field_type,
                "numeric_value": row.numeric_value,
                "boolean_value": row.boolean_value,
                "ranking_value": row.ranking_value,
            }
            for row in result.all()
        ]

    async def batch_get_template_scores(
        self, match_player_ids: list[UUID]
    ) -> dict[UUID, list[dict]]:
        """Busca scores de template para vários jogadores de uma vez."""
        if not match_player_ids:
            return {}
        stmt = (
            select(
                MatchTemplateScore.match_player_id,
                MatchTemplateScore.template_field_id,
                ScoringTemplateField.name.label("field_name"),
                ScoringTemplateField.field_type,
                MatchTemplateScore.numeric_value,
                MatchTemplateScore.boolean_value,
                MatchTemplateScore.ranking_value,
            )
            .join(
                ScoringTemplateField,
                ScoringTemplateField.id == MatchTemplateScore.template_field_id,
            )
            .where(MatchTemplateScore.match_player_id.in_(match_player_ids))
            .order_by(
                MatchTemplateScore.match_player_id,
                ScoringTemplateField.display_order,
            )
        )
        result = await self.session.execute(stmt)

        scores_map: dict[UUID, list[dict]] = {pid: [] for pid in match_player_ids}
        for row in result.all():
            scores_map[row.match_player_id].append({
                "template_field_id": row.template_field_id,
                "field_name": row.field_name,
                "field_type": row.field_type,
                "numeric_value": row.numeric_value,
                "boolean_value": row.boolean_value,
                "ranking_value": row.ranking_value,
            })
        return scores_map
