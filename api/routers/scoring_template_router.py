from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.core.security import get_current_user
from api.models.user import User
from api.schemas.scoring_template import (
    ScoringTemplateCreate,
    ScoringTemplateListResponse,
    ScoringTemplateResponse,
    ScoringTemplateUpdate,
)
from api.services.scoring_template_service import ScoringTemplateService

router = APIRouter(prefix="/scoring-templates", tags=["Scoring Templates"])


@router.post("/", response_model=ScoringTemplateResponse, status_code=201)
async def create_template(
    data: ScoringTemplateCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScoringTemplateResponse:
    service = ScoringTemplateService(session)
    return await service.create_template(data, current_user)


@router.get("/search/", response_model=list[ScoringTemplateListResponse])
async def search_templates(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> list[ScoringTemplateListResponse]:
    service = ScoringTemplateService(session)
    return await service.search_templates(q, limit)


@router.get("/game/{game_id}", response_model=list[ScoringTemplateListResponse])
async def list_templates_by_game(
    game_id: UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> list[ScoringTemplateListResponse]:
    service = ScoringTemplateService(session)
    return await service.list_templates_by_game(game_id)


@router.get("/{template_id}", response_model=ScoringTemplateResponse)
async def get_template(
    template_id: UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
) -> ScoringTemplateResponse:
    service = ScoringTemplateService(session)
    return await service.get_template(template_id)


@router.patch("/{template_id}", response_model=ScoringTemplateResponse)
async def update_template(
    template_id: UUID,
    data: ScoringTemplateUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScoringTemplateResponse:
    service = ScoringTemplateService(session)
    return await service.update_template(template_id, data, current_user)


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    service = ScoringTemplateService(session)
    await service.delete_template(template_id, current_user)
