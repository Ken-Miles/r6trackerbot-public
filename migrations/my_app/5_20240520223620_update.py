from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "Settings" ADD "preferred_platform" VARCHAR(5) NOT NULL  DEFAULT 'N/A';
        ALTER TABLE "Settings" ADD "prefix" VARCHAR(5) NOT NULL  DEFAULT '!';
        ALTER TABLE "Settings" ADD "language" VARCHAR(5) NOT NULL  DEFAULT 'en';
        ALTER TABLE "Settings" ADD "user_id" BIGINT NOT NULL UNIQUE;
        ALTER TABLE "Settings" ADD "timezone" VARCHAR(50) NOT NULL  DEFAULT 'UTC';
        ALTER TABLE "Settings" ADD "username" VARCHAR(100) NOT NULL;
        ALTER TABLE "Settings" ADD "use_custom_prefix" BOOL NOT NULL  DEFAULT False;
        ALTER TABLE "Settings" ADD "show_on_leaderboard" BOOL NOT NULL  DEFAULT True;
        ALTER TABLE "Settings" ADD "color" VARCHAR(7) NOT NULL  DEFAULT '#7289DA';
        ALTER TABLE "Settings" DROP COLUMN "default";
        ALTER TABLE "Settings" DROP COLUMN "emoji";
        ALTER TABLE "Settings" DROP COLUMN "settingtype";
        ALTER TABLE "Settings" DROP COLUMN "name";
        ALTER TABLE "Settings" DROP COLUMN "description";
        ALTER TABLE "Settings" DROP COLUMN "valuetype";
        CREATE TABLE IF NOT EXISTS "SettingsInfo" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(100) NOT NULL,
    "description" TEXT NOT NULL,
    "valuetype" VARCHAR(100) NOT NULL,
    "emoji" VARCHAR(100),
    "min_value" INT,
    "max_value" INT
);
        DROP TABLE IF EXISTS "UserSettings";
        DROP TABLE IF EXISTS "GuildSettings";
        CREATE UNIQUE INDEX "uid_Settings_user_id_655cc4" ON "Settings" ("user_id");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX "idx_Settings_user_id_655cc4";
        ALTER TABLE "Settings" ADD "default" TEXT;
        ALTER TABLE "Settings" ADD "emoji" TEXT;
        ALTER TABLE "Settings" ADD "settingtype" TEXT NOT NULL;
        ALTER TABLE "Settings" ADD "name" TEXT NOT NULL;
        ALTER TABLE "Settings" ADD "description" TEXT NOT NULL;
        ALTER TABLE "Settings" ADD "valuetype" TEXT NOT NULL;
        ALTER TABLE "Settings" DROP COLUMN "preferred_platform";
        ALTER TABLE "Settings" DROP COLUMN "prefix";
        ALTER TABLE "Settings" DROP COLUMN "language";
        ALTER TABLE "Settings" DROP COLUMN "user_id";
        ALTER TABLE "Settings" DROP COLUMN "timezone";
        ALTER TABLE "Settings" DROP COLUMN "username";
        ALTER TABLE "Settings" DROP COLUMN "use_custom_prefix";
        ALTER TABLE "Settings" DROP COLUMN "show_on_leaderboard";
        ALTER TABLE "Settings" DROP COLUMN "color";
        DROP TABLE IF EXISTS "SettingsInfo";"""
