from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.match import Match
from api.models.match_player import MatchPlayer
from api.models.user import User
from api.repositories.game_repository import GameRepository
from api.repositories.match_repository import MatchRepository
from api.repositories.user_repository import UserRepository
from api.schemas.match import MatchCreate, MatchPlayerResponse, MatchResponse


class MatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.match_repo = MatchRepository(session)
        self.game_repo = GameRepository(session)
        self.user_repo = UserRepository(session)

    async def create_match(
        self, data: MatchCreate, current_user: User
    ) -> MatchResponse:
        # Validar jogo
        game = await self.game_repo.get_by_id(data.game_id)
        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Jogo não encontrado",
            )

        # Validar quantidade de jogadores
        num_players = len(data.players)
        if num_players < game.min_players or num_players > game.max_players:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Número de jogadores deve ser entre {game.min_players} e {game.max_players}",
            )

        # Validar jogadores existem
        user_ids = [p.user_id for p in data.players]
        if len(set(user_ids)) != len(user_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Jogadores duplicados na partida",
            )

        for user_id in user_ids:
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Usuário {user_id} não encontrado",
                )

        # Criar partida
        played_at = data.played_at or datetime.now(timezone.utc)
        match = Match(
            game_id=data.game_id,
            created_by=current_user.id,
            played_at=played_at.replace(tzinfo=None),
            notes=data.notes,
        )
        created_match = await self.match_repo.create_match(match)

        # Criar jogadores da partida
        match_players = [
            MatchPlayer(
                match_id=created_match.id,
                user_id=p.user_id,
                position=p.position,
                score=p.score,
                is_winner=p.is_winner,
            )
            for p in data.players
        ]
        created_players = await self.match_repo.create_match_players(match_players)

        return MatchResponse(
            id=created_match.id,
            game_id=created_match.game_id,
            game_name=game.name,
            created_by=created_match.created_by,
            played_at=created_match.played_at,
            notes=created_match.notes,
            created_at=created_match.created_at,
            players=[
                MatchPlayerResponse(
                    id=mp.id,
                    user_id=mp.user_id,
                    position=mp.position,
                    score=mp.score,
                    is_winner=mp.is_winner,
                )
                for mp in created_players
            ],
        )

    async def get_match(self, match_id: UUID) -> MatchResponse:
        match_data = await self.match_repo.get_match_with_details(match_id)
        if not match_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partida não encontrada",
            )

        players = await self.match_repo.get_match_players_with_username(match_id)

        return MatchResponse(
            id=match_data["id"],
            game_id=match_data["game_id"],
            game_name=match_data["game_name"],
            created_by=match_data["created_by"],
            played_at=match_data["played_at"],
            notes=match_data["notes"],
            created_at=match_data["created_at"],
            players=[
                MatchPlayerResponse(
                    id=p["id"],
                    user_id=p["user_id"],
                    username=p["username"],
                    position=p["position"],
                    score=p["score"],
                    is_winner=p["is_winner"],
                )
                for p in players
            ],
        )

    async def get_user_matches(
        self, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[MatchResponse]:
        matches = await self.match_repo.get_user_matches_with_details(
            user_id, skip=skip, limit=limit
        )
        return [
            MatchResponse(
                id=m["id"],
                game_id=m["game_id"],
                game_name=m["game_name"],
                created_by=m["created_by"],
                played_at=m["played_at"],
                notes=m["notes"],
                created_at=m["created_at"],
                players=[
                    MatchPlayerResponse(
                        id=p["id"],
                        user_id=p["user_id"],
                        username=p["username"],
                        position=p["position"],
                        score=p["score"],
                        is_winner=p["is_winner"],
                    )
                    for p in m["players"]
                ],
            )
            for m in matches
        ]
