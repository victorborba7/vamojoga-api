"""
Minimal migration script — applies ALTER TABLE statements that are safe to run
multiple times (uses IF NOT EXISTS / checks before altering).
Run before starting the API server.
"""
import asyncio

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from api.core.config import settings

DATABASE_URL = settings.DATABASE_URL


MIGRATIONS = [
    # Add match_mode to matches (added after initial schema creation)
    """
    ALTER TABLE matches
        ADD COLUMN IF NOT EXISTS match_mode VARCHAR(50) NOT NULL DEFAULT 'individual';
    """,
    # Add scoring_template_id to matches if missing
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'matches' AND column_name = 'scoring_template_id'
        ) THEN
            ALTER TABLE matches ADD COLUMN scoring_template_id UUID REFERENCES scoring_templates(id);
        END IF;
    END$$;
    """,
    # Remove duplicate user_achievements before adding unique constraint
    """
    DELETE FROM user_achievements ua1
    USING user_achievements ua2
    WHERE ua1.unlocked_at > ua2.unlocked_at
      AND ua1.user_id = ua2.user_id
      AND ua1.achievement_id = ua2.achievement_id;
    """,
    # Add unique constraint to prevent duplicate achievements per user
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_user_achievement'
        ) THEN
            ALTER TABLE user_achievements
                ADD CONSTRAINT uq_user_achievement UNIQUE (user_id, achievement_id);
        END IF;
    END$$;
    """,
    # Re-point user_achievements referencing duplicate achievements to the kept (oldest) record,
    # then delete the duplicate achievements.
    # "Kept" = lowest created_at for each (type, game_id, criteria_key, criteria_value) group.
    """
    DO $$
    DECLARE
        dup RECORD;
        kept_id UUID;
    BEGIN
        FOR dup IN
            SELECT type, game_id, criteria_key, criteria_value
            FROM achievements
            GROUP BY type, game_id, criteria_key, criteria_value
            HAVING COUNT(*) > 1
        LOOP
            -- Pick the oldest record to keep
            SELECT id INTO kept_id
            FROM achievements
            WHERE type           = dup.type
              AND (game_id       = dup.game_id OR (game_id IS NULL AND dup.game_id IS NULL))
              AND criteria_key   = dup.criteria_key
              AND criteria_value = dup.criteria_value
            ORDER BY created_at ASC
            LIMIT 1;

            -- Move user_achievements pointing to duplicates to the kept record
            UPDATE user_achievements
               SET achievement_id = kept_id
             WHERE achievement_id IN (
                SELECT id FROM achievements
                WHERE type           = dup.type
                  AND (game_id       = dup.game_id OR (game_id IS NULL AND dup.game_id IS NULL))
                  AND criteria_key   = dup.criteria_key
                  AND criteria_value = dup.criteria_value
                  AND id            <> kept_id
             )
               AND NOT EXISTS (
                   -- avoid creating a new duplicate in user_achievements
                   SELECT 1 FROM user_achievements ua2
                   WHERE ua2.user_id        = user_achievements.user_id
                     AND ua2.achievement_id = kept_id
               );

            -- Delete orphaned user_achievements still pointing to duplicates
            DELETE FROM user_achievements
             WHERE achievement_id IN (
                SELECT id FROM achievements
                WHERE type           = dup.type
                  AND (game_id       = dup.game_id OR (game_id IS NULL AND dup.game_id IS NULL))
                  AND criteria_key   = dup.criteria_key
                  AND criteria_value = dup.criteria_value
                  AND id            <> kept_id
             );

            -- Delete the duplicate achievement rows
            DELETE FROM achievements
             WHERE type           = dup.type
               AND (game_id       = dup.game_id OR (game_id IS NULL AND dup.game_id IS NULL))
               AND criteria_key   = dup.criteria_key
               AND criteria_value = dup.criteria_value
               AND id            <> kept_id;
        END LOOP;
    END$$;
    """,
    # Add unique constraint on achievements to prevent future duplicates
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_achievement_criteria'
        ) THEN
            ALTER TABLE achievements
                ADD CONSTRAINT uq_achievement_criteria
                UNIQUE (type, game_id, criteria_key, criteria_value);
        END IF;
    END$$;
    """,
]


async def run_migrations() -> None:
    engine = create_async_engine(DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        for migration in MIGRATIONS:
            await conn.execute(text(migration))
    await engine.dispose()
    print("Migrations applied successfully.")


if __name__ == "__main__":
    asyncio.run(run_migrations())
