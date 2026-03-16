import asyncio
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.match import Match
from api.models.match_player import MatchPlayer
from api.models.match_expansion import MatchExpansion
from api.models.scoring_template import MatchTemplateScore
from api.models.user import User
from api.repositories.guest_repository import GuestRepository
from api.repositories.friendship_repository import FriendshipRepository
from api.repositories.game_repository import GameRepository
from api.repositories.match_repository import MatchRepository
from api.repositories.scoring_template_repository import ScoringTemplateRepository
from api.repositories.user_repository import UserRepository
from api.schemas.match import MatchCreate, MatchPlayerResponse, MatchResponse, PlayerScoreSubmit, ExpansionInfo
from api.schemas.scoring_template import MatchTemplateScoreResponse
from api.services.achievement_service import AchievementService
from api.services.push_service import PushService


class MatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.match_repo = MatchRepository(session)
        self.game_repo = GameRepository(session)
        self.user_repo = UserRepository(session)
        self.guest_repo = GuestRepository(session)
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
        # if num_players < game.min_players or num_players > game.max_players:
        #     raise HTTPException(
        #         status_code=status.HTTP_400_BAD_REQUEST,
        #         detail=f"Número de jogadores deve ser entre {game.min_players} e {game.max_players}",
        #     )

        # Validar jogadores/convidados
        user_ids: list[UUID] = []
        guest_ids: list[UUID] = []
        participant_keys: set[tuple[str, UUID]] = set()
        for p in data.players:
            if (p.user_id is None and p.guest_id is None) or (p.user_id is not None and p.guest_id is not None):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cada participante deve ter user_id ou guest_id (apenas um)",
                )

            if p.user_id is not None:
                key = ("u", p.user_id)
                user_ids.append(p.user_id)
            else:
                key = ("g", p.guest_id)
                guest_ids.append(p.guest_id)

            if key in participant_keys:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Participantes duplicados na partida",
                )
            participant_keys.add(key)

        # Guests do not self-submit scores
        if data.collaborative_scoring and guest_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Partidas colaborativas nao permitem convidados",
            )

        found_users = await self.user_repo.get_by_ids(user_ids)
        user_map = {u.id: u for u in found_users}
        if len(found_users) != len(user_ids):
            missing = [uid for uid in user_ids if uid not in user_map]
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuario {missing[0]} nao encontrado")

        found_guests = await self.guest_repo.get_by_ids(guest_ids)
        guest_map = {g.id: g for g in found_guests}
        if len(found_guests) != len(guest_ids):
            missing = [gid for gid in guest_ids if gid not in guest_map]
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Convidado {missing[0]} nao encontrado")
        invalid_owner = [g.id for g in found_guests if g.owner_id != current_user.id]
        if invalid_owner:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Convidado nao pertence ao usuario atual")

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
                guest_id=p.guest_id,
                position=p.position if not is_collaborative else 0,
                score=p.score if not is_collaborative else 0,
                is_winner=p.is_winner if not is_collaborative else False,
                scores_submitted=not is_collaborative,
            )
            for p in data.players
        ]
        created_players = await self.match_repo.create_match_players(match_players)

        # Salvar expansões utilizadas
        expansion_infos: list[ExpansionInfo] = []
        if data.expansion_ids:
            for exp_id in data.expansion_ids:
                exp_game = await self.game_repo.get_by_id(exp_id)
                if exp_game:
                    self.session.add(MatchExpansion(match_id=created_match.id, game_id=exp_id))
                    expansion_infos.append(ExpansionInfo(
                        id=exp_game.id,
                        name=exp_game.name,
                        name_pt=exp_game.name_pt,
                        image_url=exp_game.image_url,
                    ))
            await self.session.flush()
        if not is_collaborative:
            player_map = {
                (("u", p.user_id) if p.user_id is not None else ("g", p.guest_id)): mp
                for p, mp in zip(data.players, created_players)
            }
            for p_data in data.players:
                if p_data.template_scores:
                    key = ("u", p_data.user_id) if p_data.user_id is not None else ("g", p_data.guest_id)
                    scores = [
                        MatchTemplateScore(
                            match_player_id=player_map[key].id,
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
                if p_data.user_id is not None and p_data.user_id != current_user.id:
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
                        guest_id=mp.guest_id,
                        username=user_map.get(mp.user_id).username if mp.user_id in user_map else None,
                        guest_name=guest_map.get(mp.guest_id).name if mp.guest_id in guest_map else None,
                        participant_name=(user_map.get(mp.user_id).username if mp.user_id in user_map else None)
                        or (guest_map.get(mp.guest_id).name if mp.guest_id in guest_map else None),
                        position=mp.position,
                        score=mp.score,
                        is_winner=mp.is_winner,
                        scores_submitted=mp.scores_submitted,
                    )
                    for mp in created_players
                ],
                expansions=expansion_infos,
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
                    guest_id=mp.guest_id,
                    username=user_map.get(mp.user_id).username if mp.user_id in user_map else None,
                    guest_name=guest_map.get(mp.guest_id).name if mp.guest_id in guest_map else None,
                    participant_name=(user_map.get(mp.user_id).username if mp.user_id in user_map else None)
                    or (guest_map.get(mp.guest_id).name if mp.guest_id in guest_map else None),
                    position=mp.position,
                    score=mp.score,
                    is_winner=mp.is_winner,
                    scores_submitted=mp.scores_submitted,
                )
                for mp in created_players
            ],
            expansions=expansion_infos,
        )

    async def _award_achievements_and_notify(
        self,
        players_data,
        match_id,
        game_id,
        current_user,
        game,
        notify_friends_about_registration: bool = True,
    ):
        all_unlocked = []
        participant_user_ids: set[UUID] = set()
        for p_data in players_data:
            uid = p_data.user_id if hasattr(p_data, 'user_id') else p_data
            if uid is None:
                continue
            participant_user_ids.add(uid)
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
                    if friend_id not in participant_user_ids:
                        continue
                    if friend_id == current_user.id:
                        continue
                    await self.push_service.send_to_user(
                        friend_id,
                        f"{current_user.username} registrou uma partida",
                        f"{game.name} • {num_players} jogadores",
                        "/matches",
                    )
            except Exception:
                pass

        if notify_friends_about_registration:
            asyncio.create_task(_notify_friends())
        return all_unlocked

    async def submit_player_scores(
        self, match_id: UUID, target_user_id: UUID,
        data: PlayerScoreSubmit, current_user: User,
    ) -> MatchResponse:
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

        # Check if all players have submitted — auto-finalize
        all_players = await self.match_repo.get_match_players(match_id)
        all_submitted = all(p.scores_submitted for p in all_players)
        if all_submitted:
            return await self._do_finalize(match, all_players, current_user)

        # Notify the organizer that a player submitted
        if current_user.id != match.created_by:
            asyncio.create_task(
                self.push_service.send_to_user(
                    match.created_by,
                    f"{current_user.username} registrou sua pontuação",
                    "Aguardando os demais jogadores",
                    f"/matches/{match_id}",
                )
            )

        return await self.get_match(match_id)

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

        players = await self.match_repo.get_match_players(match_id)
        return await self._do_finalize(match, players, current_user)

    async def _do_finalize(self, match, players, current_user: User) -> MatchResponse:
        game = await self.game_repo.get_by_id(match.game_id)
        template = None
        if match.scoring_template_id:
            template = await self.template_repo.get_template_by_id(match.scoring_template_id)

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

        # Notify all players that the match is finalized
        winner = next((p for p in players if p.is_winner), None)
        winner_user = None
        if winner:
            found = await self.user_repo.get_by_ids([winner.user_id])
            winner_user = found[0] if found else None

        for mp in players:
            if mp.user_id is not None and mp.user_id != current_user.id:
                asyncio.create_task(
                    self.push_service.send_to_user(
                        mp.user_id,
                        "Partida finalizada! 🏆",
                        f"Vencedor: {winner_user.username if winner_user else '?'} — veja o ranking",
                        f"/matches/{match.id}",
                    )
                )

        # Award achievements
        all_unlocked = await self._award_achievements_and_notify(
            players,
            match.id,
            match.game_id,
            current_user,
            game,
            notify_friends_about_registration=False,
        )

        return await self.get_match(match.id, unlocked_achievements=all_unlocked)

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
                    guest_id=p.get("guest_id"),
                    username=p["username"],
                    guest_name=p.get("guest_name"),
                    participant_name=p["username"] or p.get("guest_name"),
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
                        guest_id=p.get("guest_id"),
                        username=p["username"],
                        guest_name=p.get("guest_name"),
                        participant_name=p["username"] or p.get("guest_name"),
                        position=p["position"],
                        score=p["score"],
                        is_winner=p["is_winner"],
                        scores_submitted=p.get("scores_submitted", False),
                        scores_submitted_at=p.get("scores_submitted_at"),
                    )
                    for p in m["players"]
                ],
                expansions=[
                    ExpansionInfo(
                        id=e["id"],
                        name=e["name"],
                        name_pt=e.get("name_pt"),
                        image_url=e.get("image_url"),
                    )
                    for e in m.get("expansions", [])
                ],
            )
            for m in matches
        ]
