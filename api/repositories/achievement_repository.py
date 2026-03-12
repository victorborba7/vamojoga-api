from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.achievement import Achievement, UserAchievement
from api.models.friendship import Friendship
from api.models.match_player import MatchPlayer
from api.models.user import User


class AchievementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Achievement CRUD ──

    async def create_achievement(self, achievement: Achievement) -> Achievement:
        self.session.add(achievement)
        await self.session.commit()
        await self.session.refresh(achievement)
        return achievement

    async def bulk_upsert_achievements(self, achievements: list[Achievement]) -> int:
        """Insert achievements, skipping those whose criteria already exist. Returns count created."""
        created = 0
        for a in achievements:
            existing = await self.get_achievement_by_criteria(
                a.type, a.game_id, a.criteria_key, a.criteria_value
            )
            if not existing:
                self.session.add(a)
                created += 1
        if created:
            await self.session.commit()
        return created

    async def get_achievement_by_id(self, achievement_id: UUID) -> Achievement | None:
        stmt = select(Achievement).where(Achievement.id == achievement_id, Achievement.is_active)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_achievement_by_name(self, name: str) -> Achievement | None:
        stmt = select(Achievement).where(Achievement.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_achievement_by_criteria(
        self,
        type_: str,
        game_id: UUID | None,
        criteria_key: str,
        criteria_value: int,
    ) -> Achievement | None:
        stmt = select(Achievement).where(
            Achievement.type == type_,
            Achievement.game_id == game_id,
            Achievement.criteria_key == criteria_key,
            Achievement.criteria_value == criteria_value,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_global_achievements(self) -> list[Achievement]:
        stmt = (
            select(Achievement)
            .where(Achievement.type == "global", Achievement.is_active)
            .order_by(Achievement.criteria_key, Achievement.criteria_value)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_game_achievements(self, game_id: UUID) -> list[Achievement]:
        stmt = (
            select(Achievement)
            .where(Achievement.type == "game", Achievement.game_id == game_id, Achievement.is_active)
            .order_by(Achievement.criteria_key, Achievement.criteria_value)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ── UserAchievement ──

    async def get_user_achievement_ids(self, user_id: UUID) -> set[UUID]:
        """Return set of achievement IDs already unlocked by user."""
        stmt = select(UserAchievement.achievement_id).where(UserAchievement.user_id == user_id)
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def create_user_achievement(self, ua: UserAchievement) -> UserAchievement | None:
        """Insert the user achievement, silently ignoring duplicates (race-condition safe)."""
        stmt = (
            pg_insert(UserAchievement)
            .values(
                id=ua.id,
                user_id=ua.user_id,
                achievement_id=ua.achievement_id,
                match_id=ua.match_id,
                unlocked_at=ua.unlocked_at,
            )
            .on_conflict_do_nothing(constraint="uq_user_achievement")
            .returning(UserAchievement)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        row = result.scalar_one_or_none()
        return row

    async def get_user_achievements(self, user_id: UUID) -> list[dict]:
        stmt = (
            select(
                UserAchievement.id,
                UserAchievement.user_id,
                UserAchievement.achievement_id,
                UserAchievement.match_id,
                UserAchievement.unlocked_at,
                Achievement.name.label("achievement_name"),
                Achievement.description.label("achievement_description"),
                Achievement.icon_url.label("achievement_icon_url"),
                Achievement.type.label("achievement_type"),
                Achievement.points.label("achievement_points"),
            )
            .join(Achievement, Achievement.id == UserAchievement.achievement_id)
            .where(UserAchievement.user_id == user_id)
            .order_by(UserAchievement.unlocked_at.desc())
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get_user_achievements_with_username(self, user_id: UUID) -> list[dict]:
        stmt = (
            select(
                UserAchievement.id,
                UserAchievement.user_id,
                User.username,
                UserAchievement.achievement_id,
                UserAchievement.match_id,
                UserAchievement.unlocked_at,
                Achievement.name.label("achievement_name"),
                Achievement.description.label("achievement_description"),
                Achievement.icon_url.label("achievement_icon_url"),
                Achievement.type.label("achievement_type"),
                Achievement.points.label("achievement_points"),
            )
            .join(Achievement, Achievement.id == UserAchievement.achievement_id)
            .join(User, User.id == UserAchievement.user_id)
            .where(UserAchievement.user_id == user_id)
            .order_by(UserAchievement.unlocked_at.desc())
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    # ── Stats queries for criteria evaluation ──

    async def count_user_matches(self, user_id: UUID) -> int:
        stmt = select(func.count()).select_from(MatchPlayer).where(MatchPlayer.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_user_wins(self, user_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(MatchPlayer)
            .where(MatchPlayer.user_id == user_id, MatchPlayer.is_winner.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_user_unique_games(self, user_id: UUID) -> int:
        from api.models.match import Match

        stmt = (
            select(func.count(func.distinct(Match.game_id)))
            .select_from(MatchPlayer)
            .join(Match, Match.id == MatchPlayer.match_id)
            .where(MatchPlayer.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_user_friends(self, user_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Friendship)
            .where(
                Friendship.status == "accepted",
                (Friendship.requester_id == user_id) | (Friendship.addressee_id == user_id),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_user_game_matches(self, user_id: UUID, game_id: UUID) -> int:
        from api.models.match import Match

        stmt = (
            select(func.count())
            .select_from(MatchPlayer)
            .join(Match, Match.id == MatchPlayer.match_id)
            .where(MatchPlayer.user_id == user_id, Match.game_id == game_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_user_game_wins(self, user_id: UUID, game_id: UUID) -> int:
        from api.models.match import Match

        stmt = (
            select(func.count())
            .select_from(MatchPlayer)
            .join(Match, Match.id == MatchPlayer.match_id)
            .where(
                MatchPlayer.user_id == user_id,
                MatchPlayer.is_winner.is_(True),
                Match.game_id == game_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
