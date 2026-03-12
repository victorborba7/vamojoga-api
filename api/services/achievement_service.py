from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.achievement import Achievement, UserAchievement, VALID_ACHIEVEMENT_TYPES
from api.repositories.achievement_repository import AchievementRepository
from api.schemas.achievement import (
    AchievementCreate,
    AchievementImport,
    AchievementResponse,
    NewlyUnlockedAchievement,
    UserAchievementResponse,
)

# Maps criteria_key to the repository method that returns the current count
GLOBAL_CRITERIA_KEYS = ("matches_played", "wins", "unique_games", "friends")
GAME_CRITERIA_KEYS = ("game_matches", "game_wins")


class AchievementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AchievementRepository(session)

    # ── Read ──

    async def get_global_achievements(self) -> list[AchievementResponse]:
        rows = await self.repo.get_global_achievements()
        return [AchievementResponse.model_validate(r) for r in rows]

    async def get_game_achievements(self, game_id: UUID) -> list[AchievementResponse]:
        rows = await self.repo.get_game_achievements(game_id)
        return [AchievementResponse.model_validate(r) for r in rows]

    async def get_user_achievements(self, user_id: UUID) -> list[UserAchievementResponse]:
        rows = await self.repo.get_user_achievements_with_username(user_id)
        return [UserAchievementResponse(**r) for r in rows]

    # ── Import ──

    async def import_achievements(self, data: AchievementImport) -> int:
        """Import achievements from external payload, skipping duplicates by name. Returns count created."""
        models: list[Achievement] = []
        for a in data.achievements:
            if a.type not in VALID_ACHIEVEMENT_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tipo de conquista inválido: {a.type}",
                )
            if a.type == "game" and not a.game_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Conquista do tipo 'game' precisa de game_id: {a.name}",
                )
            models.append(
                Achievement(
                    name=a.name,
                    description=a.description,
                    icon_url=a.icon_url,
                    type=a.type,
                    game_id=a.game_id,
                    criteria_key=a.criteria_key,
                    criteria_value=a.criteria_value,
                    points=a.points,
                )
            )
        return await self.repo.bulk_upsert_achievements(models)

    # ── Criteria evaluation engine ──

    async def _get_stat(self, user_id: UUID, criteria_key: str, game_id: UUID | None = None) -> int:
        """Resolve a criteria_key to the user's current stat value."""
        if criteria_key == "matches_played":
            return await self.repo.count_user_matches(user_id)
        if criteria_key == "wins":
            return await self.repo.count_user_wins(user_id)
        if criteria_key == "unique_games":
            return await self.repo.count_user_unique_games(user_id)
        if criteria_key == "friends":
            return await self.repo.count_user_friends(user_id)
        if criteria_key == "game_matches" and game_id:
            return await self.repo.count_user_game_matches(user_id, game_id)
        if criteria_key == "game_wins" and game_id:
            return await self.repo.count_user_game_wins(user_id, game_id)
        return 0

    async def check_and_award(
        self,
        user_id: UUID,
        match_id: UUID | None = None,
        game_id: UUID | None = None,
    ) -> list[NewlyUnlockedAchievement]:
        """
        Evaluate all active achievements against the user's current stats.
        Awards any that haven't been unlocked yet and whose criteria are met.
        Returns list of newly unlocked achievements.
        """
        already_unlocked = await self.repo.get_user_achievement_ids(user_id)

        # Check global achievements
        global_achievements = await self.repo.get_global_achievements()
        # Check game-specific achievements if game_id provided
        game_achievements = await self.repo.get_game_achievements(game_id) if game_id else []

        candidates = global_achievements + game_achievements
        newly_unlocked: list[NewlyUnlockedAchievement] = []

        for achievement in candidates:
            if achievement.id in already_unlocked:
                continue

            stat = await self._get_stat(user_id, achievement.criteria_key, achievement.game_id)
            if stat >= achievement.criteria_value:
                ua = UserAchievement(
                    user_id=user_id,
                    achievement_id=achievement.id,
                    match_id=match_id,
                )
                inserted = await self.repo.create_user_achievement(ua)
                if inserted is not None:
                    newly_unlocked.append(
                        NewlyUnlockedAchievement(
                            id=achievement.id,
                            name=achievement.name,
                            description=achievement.description,
                            icon_url=achievement.icon_url,
                            points=achievement.points,
                        )
                    )

        return newly_unlocked
