from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.scoring_template import (
    ScoringTemplate,
    ScoringTemplateField,
)
from api.models.user import User
from api.repositories.game_repository import GameRepository
from api.repositories.scoring_template_repository import ScoringTemplateRepository
from api.schemas.scoring_template import (
    VALID_FIELD_TYPES,
    ScoringTemplateCreate,
    ScoringTemplateFieldResponse,
    ScoringTemplateListResponse,
    ScoringTemplateResponse,
    ScoringTemplateUpdate,
)


class ScoringTemplateService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = ScoringTemplateRepository(session)
        self.game_repo = GameRepository(session)

    async def create_template(
        self, data: ScoringTemplateCreate, current_user: User
    ) -> ScoringTemplateResponse:
        # Validate game exists
        game = await self.game_repo.get_by_id(data.game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jogo não encontrado",
            )

        # Validate field types
        for f in data.fields:
            if f.field_type not in VALID_FIELD_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tipo de campo inválido: '{f.field_type}'. Use: {', '.join(VALID_FIELD_TYPES)}",
                )
            if f.min_value is not None and f.max_value is not None and f.min_value > f.max_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Campo '{f.name}': min_value não pode ser maior que max_value",
                )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        template = ScoringTemplate(
            game_id=data.game_id,
            created_by=current_user.id,
            name=data.name,
            description=data.description,
            created_at=now,
            updated_at=now,
        )
        created = await self.repo.create_template(template)

        fields = [
            ScoringTemplateField(
                template_id=created.id,
                name=f.name,
                field_type=f.field_type,
                min_value=f.min_value,
                max_value=f.max_value,
                display_order=f.display_order,
                is_required=f.is_required,
                is_tiebreaker=f.is_tiebreaker,
            )
            for f in data.fields
        ]
        created_fields = await self.repo.create_fields(fields)

        return ScoringTemplateResponse(
            id=created.id,
            game_id=created.game_id,
            game_name=game.name,
            created_by=created.created_by,
            created_by_username=current_user.username,
            name=created.name,
            description=created.description,
            is_active=created.is_active,
            fields=[
                ScoringTemplateFieldResponse(
                    id=f.id,
                    name=f.name,
                    field_type=f.field_type,
                    min_value=f.min_value,
                    max_value=f.max_value,
                    display_order=f.display_order,
                    is_required=f.is_required,
                )
                for f in created_fields
            ],
            created_at=created.created_at,
            updated_at=created.updated_at,
        )

    async def get_template(self, template_id: UUID) -> ScoringTemplateResponse:
        data = await self.repo.get_template_with_details(template_id)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template não encontrado",
            )

        fields = await self.repo.get_template_fields(template_id)

        return ScoringTemplateResponse(
            id=data["id"],
            game_id=data["game_id"],
            game_name=data["game_name"],
            created_by=data["created_by"],
            created_by_username=data["created_by_username"],
            name=data["name"],
            description=data["description"],
            is_active=data["is_active"],
            fields=[
                ScoringTemplateFieldResponse(
                    id=f.id,
                    name=f.name,
                    field_type=f.field_type,
                    min_value=f.min_value,
                    max_value=f.max_value,
                    display_order=f.display_order,
                    is_required=f.is_required,
                )
                for f in fields
            ],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    async def list_templates_by_game(
        self, game_id: UUID
    ) -> list[ScoringTemplateListResponse]:
        templates = await self.repo.list_templates_by_game(game_id)
        return [
            ScoringTemplateListResponse(**t)
            for t in templates
        ]

    async def search_templates(
        self, query: str, limit: int = 20
    ) -> list[ScoringTemplateListResponse]:
        templates = await self.repo.search_templates(query, limit)
        return [
            ScoringTemplateListResponse(**t)
            for t in templates
        ]

    async def update_template(
        self,
        template_id: UUID,
        data: ScoringTemplateUpdate,
        current_user: User,
    ) -> ScoringTemplateResponse:
        template = await self.repo.get_template_by_id(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template não encontrado",
            )

        if template.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas o criador pode editar este template",
            )

        if data.name is not None:
            template.name = data.name
        if data.description is not None:
            template.description = data.description
        if data.is_active is not None:
            template.is_active = data.is_active
        template.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await self.repo.update_template(template)
        return await self.get_template(template_id)

    async def delete_template(
        self, template_id: UUID, current_user: User
    ) -> None:
        template = await self.repo.get_template_by_id(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template não encontrado",
            )

        if template.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas o criador pode desativar este template",
            )

        template.is_active = False
        template.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.repo.update_template(template)
