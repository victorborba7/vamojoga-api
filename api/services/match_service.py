import asyncio
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.match import Match
from api.models.match_player import MatchPlayer
from api.models.scoring_template import MatchTemplateScore
from api.models.user import User
from api.repositories.friendship_repository import FriendshipRepository
from api.repositories.game_repository import GameRepository
from api.repositories.match_repository import MatchRepository
from api.repositories.scoring_template_repository import ScoringTemplateRepository
from api.repositories.user_repository import UserRepository
from api.schemas.match import MatchCreate, MatchPlayerResponse, MatchResponse
from api.schemas.scoring_template import MatchTemplateScoreResponse
from api.services.achievement_service import AchievementService
from api.services.push_service import PushService


class MatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.match_repo = MatchRepository(session)
        self.game_repo = GameRepository(session)
        self.user_repo = UserRepository(session)
        self.template_repo = ScoringTemplateRepository(session)
        self.achievement_service = AchievementService(session)
        self.push_service = PushService(session)
        self.friendship_repo = FriendshipRepository(session)

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

        found_users = await self.user_repo.get_by_ids(user_ids)
        if len(found_users) != len(user_ids):
            found_ids = {u.id for u in found_users}
            missing = [uid for uid in user_ids if uid not in found_ids]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuário {missing[0]} não encontrado",
            )

        # Validar template se fornecido
        template_name = None
        if data.scoring_template_id:
            template = await self.template_repo.get_template_by_id(data.scoring_template_id)
            if not template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Template de pontuação não encontrado",
                )
            if not template.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Template de pontuação está inativo",
                )
            if template.match_mode != data.match_mode:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Modo da partida '{data.match_mode}' não é compatível com o template (esperado: '{template.match_mode}')",
                )
            template_name = template.name

        # Criar partida
        played_at = data.played_at or datetime.now(timezone.utc)
        match = Match(
            game_id=data.game_id,
            created_by=current_user.id,
            played_at=played_at.replace(tzinfo=None),
            notes=data.notes,
            match_mode=data.match_mode,
            scoring_template_id=data.scoring_template_id,
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

        # Criar scores de template se houver
        player_map = {p.user_id: mp for p, mp in zip(data.players, created_players)}
        for p_data in data.players:
            if p_data.template_scores:
                scores = [
                    MatchTemplateScore(
                        match_player_id=player_map[p_data.user_id].id,
                        template_field_id=ts.template_field_id,
                        numeric_value=ts.numeric_value,
                        boolean_value=ts.boolean_value,
                        ranking_value=ts.ranking_value,
                    )
                    for ts in p_data.template_scores
                ]
                await self.template_repo.create_match_template_scores(scores)

        # Auto-award achievements for all players in the match
        all_unlocked = []
        for p_data in data.players:
            unlocked = await self.achievement_service.check_and_award(
                user_id=p_data.user_id,
                match_id=created_match.id,
                game_id=data.game_id,
            )
            all_unlocked.extend(unlocked)
            # Push for each unlocked achievement
            for achievement in unlocked:
                asyncio.create_task(
                    self.push_service.send_to_user(
                        p_data.user_id,
                        "Conquista desbloqueada! 🏆",
                        achievement.name,
                        "/achievements",
                    )
                )

        # Notify friends of the match creator
        async def _notify_friends() -> None:
            try:
                friendships = await self.friendship_repo.get_friends(current_user.id)
                friend_ids = [
                    f.addressee_id if f.requester_id == current_user.id else f.requester_id
                    for f in friendships
                ]
                for friend_id in friend_ids:
                    await self.push_service.send_to_user(
                        friend_id,
                        f"{current_user.username} registrou uma partida",
                        f"{game.name} • {len(data.players)} jogadores",
                        "/matches",
                    )
            except Exception:
                pass

        asyncio.create_task(_notify_friends())

        return MatchResponse(
            id=created_match.id,
            game_id=created_match.game_id,
            game_name=game.name,
            game_image_url=game.image_url,
            created_by=created_match.created_by,
            played_at=created_match.played_at,
            notes=created_match.notes,
            match_mode=created_match.match_mode,
            scoring_template_id=created_match.scoring_template_id,
            scoring_template_name=template_name,
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
            unlocked_achievements=all_unlocked,
        )

    async def get_match(self, match_id: UUID) -> MatchResponse:
        match_data = await self.match_repo.get_match_with_details(match_id)
        if not match_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partida não encontrada",
            )

        players = await self.match_repo.get_match_players_with_username(match_id)

        player_responses = []
        if match_data.get("scoring_template_id"):
            player_ids = [p["id"] for p in players]
            all_scores = await self.template_repo.batch_get_template_scores(player_ids)
        else:
            all_scores = {}

        for p in players:
            ts_list = [
                MatchTemplateScoreResponse(**ts)
                for ts in all_scores.get(p["id"], [])
            ]
            player_responses.append(
                MatchPlayerResponse(
                    id=p["id"],
                    user_id=p["user_id"],
                    username=p["username"],
                    position=p["position"],
                    score=p["score"],
                    is_winner=p["is_winner"],
                    template_scores=ts_list,
                )
            )

        return MatchResponse(
            id=match_data["id"],
            game_id=match_data["game_id"],
            game_name=match_data["game_name"],
            game_image_url=match_data["game_image_url"],
            created_by=match_data["created_by"],
            played_at=match_data["played_at"],
            notes=match_data["notes"],
            match_mode=match_data["match_mode"],
            scoring_template_id=match_data.get("scoring_template_id"),
            scoring_template_name=match_data.get("scoring_template_name"),
            created_at=match_data["created_at"],
            players=player_responses,
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
                game_image_url=m["game_image_url"],
                created_by=m["created_by"],
                played_at=m["played_at"],
                notes=m["notes"],
                match_mode=m["match_mode"],
                scoring_template_id=m.get("scoring_template_id"),
                scoring_template_name=m.get("scoring_template_name"),
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
