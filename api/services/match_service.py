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
from api.schemas.match import MatchCreate, MatchPlayerResponse, MatchResponse, PlayerScoreSubmit
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
            template_name = template.name

        is_collaborative = data.collaborative_scoring and data.scoring_template_id is not None
        match_status = "pending_scores" if is_collaborative else "completed"

        # Criar partida
        played_at = data.played_at or datetime.now(timezone.utc)
        match = Match(
            game_id=data.game_id,
            created_by=current_user.id,
            played_at=played_at.replace(tzinfo=None),
            notes=data.notes,
            match_mode=data.match_mode,
            scoring_template_id=data.scoring_template_id,
            status=match_status,
        )
        created_match = await self.match_repo.create_match(match)

        # Criar jogadores da partida
        match_players = [
            MatchPlayer(
                match_id=created_match.id,
                user_id=p.user_id,
                position=p.position if not is_collaborative else 0,
                score=p.score if not is_collaborative else 0,
                is_winner=p.is_winner if not is_collaborative else False,
                scores_submitted=not is_collaborative,
            )
            for p in data.players
        ]
        created_players = await self.match_repo.create_match_players(match_players)

        # Criar scores de template se houver (only for non-collaborative)
        if not is_collaborative:
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

        # For collaborative, notify players to submit scores
        if is_collaborative:
            for p_data in data.players:
                if p_data.user_id != current_user.id:
                    asyncio.create_task(
                        self.push_service.send_to_user(
                            p_data.user_id,
                            f"{current_user.username} registrou uma partida",
                            f"Registre sua pontuação em {game.name}!",
                            f"/matches/{created_match.id}",
                        )
                    )
        else:
            # Auto-award achievements for all players in the match
            all_unlocked = await self._award_achievements_and_notify(
                data.players, created_match.id, data.game_id, current_user, game
            )

            return MatchResponse(
                id=created_match.id,
                game_id=created_match.game_id,
                game_name=game.name,
                game_image_url=game.image_url,
                created_by=created_match.created_by,
                played_at=created_match.played_at,
                notes=created_match.notes,
                match_mode=created_match.match_mode,
                status=created_match.status,
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
                        scores_submitted=mp.scores_submitted,
                    )
                    for mp in created_players
                ],
                unlocked_achievements=all_unlocked,
            )

        return MatchResponse(
            id=created_match.id,
            game_id=created_match.game_id,
            game_name=game.name,
            game_image_url=game.image_url,
            created_by=created_match.created_by,
            played_at=created_match.played_at,
            notes=created_match.notes,
            match_mode=created_match.match_mode,
            status=created_match.status,
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
                    scores_submitted=mp.scores_submitted,
                )
                for mp in created_players
            ],
        )

    async def _award_achievements_and_notify(
        self, players_data, match_id, game_id, current_user, game
    ):
        all_unlocked = []
        for p_data in players_data:
            uid = p_data.user_id if hasattr(p_data, 'user_id') else p_data
            unlocked = await self.achievement_service.check_and_award(
                user_id=uid,
                match_id=match_id,
                game_id=game_id,
            )
            all_unlocked.extend(unlocked)
            for achievement in unlocked:
                asyncio.create_task(
                    self.push_service.send_to_user(
                        uid,
                        "Conquista desbloqueada! 🏆",
                        achievement.name,
                        "/achievements",
                    )
                )

        num_players = len(players_data)

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
                        f"{game.name} • {num_players} jogadores",
                        "/matches",
                    )
            except Exception:
                pass

        asyncio.create_task(_notify_friends())
        return all_unlocked

    async def submit_player_scores(
        self, match_id: UUID, target_user_id: UUID,
        data: PlayerScoreSubmit, current_user: User,
    ) -> MatchPlayerResponse:
        match = await self.match_repo.get_match_by_id(match_id)
        if not match:
            raise HTTPException(status_code=404, detail="Partida não encontrada")
        if match.status != "pending_scores":
            raise HTTPException(status_code=400, detail="Esta partida já foi finalizada")

        # Only the player themselves or the match creator can submit
        if current_user.id != target_user_id and current_user.id != match.created_by:
            raise HTTPException(status_code=403, detail="Sem permissão para registrar pontuação deste jogador")

        match_player = await self.match_repo.get_match_player(match_id, target_user_id)
        if not match_player:
            raise HTTPException(status_code=404, detail="Jogador não encontrado nesta partida")

        # Delete existing scores if re-submitting
        await self.match_repo.delete_template_scores_for_player(match_player.id)

        # Save new scores
        if data.template_scores:
            scores = [
                MatchTemplateScore(
                    match_player_id=match_player.id,
                    template_field_id=ts.template_field_id,
                    numeric_value=ts.numeric_value,
                    boolean_value=ts.boolean_value,
                    ranking_value=ts.ranking_value,
                )
                for ts in data.template_scores
            ]
            await self.template_repo.create_match_template_scores(scores)

        # Mark as submitted
        match_player.scores_submitted = True
        match_player.scores_submitted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.match_repo.update_match_player(match_player)

        # Notify the organizer
        if current_user.id != match.created_by:
            asyncio.create_task(
                self.push_service.send_to_user(
                    match.created_by,
                    f"{current_user.username} registrou sua pontuação",
                    "Verifique a partida para finalizar",
                    f"/matches/{match_id}",
                )
            )

        return MatchPlayerResponse(
            id=match_player.id,
            user_id=match_player.user_id,
            position=match_player.position,
            score=match_player.score,
            is_winner=match_player.is_winner,
            scores_submitted=match_player.scores_submitted,
            scores_submitted_at=match_player.scores_submitted_at,
        )

    async def finalize_match(
        self, match_id: UUID, current_user: User
    ) -> MatchResponse:
        match = await self.match_repo.get_match_by_id(match_id)
        if not match:
            raise HTTPException(status_code=404, detail="Partida não encontrada")
        if match.status != "pending_scores":
            raise HTTPException(status_code=400, detail="Esta partida já foi finalizada")
        if match.created_by != current_user.id:
            raise HTTPException(status_code=403, detail="Apenas o organizador pode finalizar a partida")

        game = await self.game_repo.get_by_id(match.game_id)
        players = await self.match_repo.get_match_players(match_id)
        template = None
        template_name = None
        if match.scoring_template_id:
            template = await self.template_repo.get_template_by_id(match.scoring_template_id)
            template_name = template.name if template else None

        # Calculate scores from template
        if template:
            fields = await self.template_repo.get_template_fields(match.scoring_template_id)
            player_ids = [p.id for p in players]
            all_scores = await self.template_repo.batch_get_template_scores(player_ids)

            tiebreaker_field_ids = {str(f.id) for f in fields if f.is_tiebreaker}

            for mp in players:
                player_scores = all_scores.get(mp.id, [])
                total = 0
                for ps in player_scores:
                    if str(ps["template_field_id"]) in tiebreaker_field_ids:
                        continue
                    if ps["field_type"] == "numeric":
                        total += ps.get("numeric_value", 0) or 0
                    elif ps["field_type"] == "boolean":
                        total += 1 if ps.get("boolean_value") else 0
                mp.score = total

            # Rank by score
            sorted_players = sorted(players, key=lambda p: p.score, reverse=True)
            rank = 1
            for i, mp in enumerate(sorted_players):
                if i > 0 and mp.score < sorted_players[i - 1].score:
                    rank = i + 1
                mp.position = rank
                mp.is_winner = rank == 1

        # Update match status
        match.status = "completed"
        await self.match_repo.update_match(match)

        # Update all players
        for mp in players:
            await self.match_repo.update_match_player(mp)

        # Award achievements
        all_unlocked = await self._award_achievements_and_notify(
            players, match.id, match.game_id, current_user, game
        )

        return await self.get_match(match_id, unlocked_achievements=all_unlocked)

    async def get_match(self, match_id: UUID, unlocked_achievements=None) -> MatchResponse:
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
                    scores_submitted=p.get("scores_submitted", False),
                    scores_submitted_at=p.get("scores_submitted_at"),
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
            status=match_data.get("status", "completed"),
            scoring_template_id=match_data.get("scoring_template_id"),
            scoring_template_name=match_data.get("scoring_template_name"),
            created_at=match_data["created_at"],
            players=player_responses,
            unlocked_achievements=unlocked_achievements or [],
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
                status=m.get("status", "completed"),
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
                        scores_submitted=p.get("scores_submitted", False),
                        scores_submitted_at=p.get("scores_submitted_at"),
                    )
                    for p in m["players"]
                ],
            )
            for m in matches
        ]
