from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "ArchivedPlaytime" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "userid" VARCHAR(100) NOT NULL,
    "clearance_level" BIGINT,
    "pve_time_played" BIGINT,
    "pvp_time_played" BIGINT,
    "total_time_played" BIGINT,
    "start_date" TIMESTAMPTZ,
    "last_modified" TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS "AuthStorage" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "sessionid" VARCHAR(100) NOT NULL,
    "key" VARCHAR(3000),
    "new_key" VARCHAR(3000) NOT NULL,
    "spaceid" VARCHAR(100) NOT NULL,
    "profileid" VARCHAR(100) NOT NULL,
    "userid" VARCHAR(100) NOT NULL,
    "expiration" TIMESTAMPTZ,
    "new_expiration" TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS "Playtime" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "userid" VARCHAR(100) NOT NULL UNIQUE,
    "clearance_level" BIGINT,
    "pve_time_played" BIGINT,
    "pvp_time_played" BIGINT,
    "total_time_played" BIGINT,
    "start_date" TIMESTAMPTZ,
    "last_modified" TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS "R6User" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "userid" UUID NOT NULL UNIQUE,
    "name" VARCHAR(100) NOT NULL,
    "platform" VARCHAR(100) NOT NULL  DEFAULT 'uplay'
);
CREATE TABLE IF NOT EXISTS "R6UserConnections" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "userid" VARCHAR(100) NOT NULL,
    "name" VARCHAR(100),
    "platform" VARCHAR(100) NOT NULL,
    "platform_id" VARCHAR(100) NOT NULL,
    "is_third_party" BOOL NOT NULL  DEFAULT False,
    "profile_id" BIGINT NOT NULL REFERENCES "R6User" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "RankedStats" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "user_id" VARCHAR(100) NOT NULL,
    "platform" VARCHAR(100) NOT NULL,
    "casual_kills" BIGINT,
    "casual_deaths" BIGINT,
    "casual_wins" BIGINT,
    "casual_losses" BIGINT,
    "casual_abandons" BIGINT,
    "casual_max_rank" VARCHAR(50),
    "casual_max_rank_points" BIGINT,
    "casual_rank" VARCHAR(50),
    "casual_rank_points" BIGINT,
    "event_kills" BIGINT,
    "event_deaths" BIGINT,
    "event_wins" BIGINT,
    "event_losses" BIGINT,
    "event_abandons" BIGINT,
    "event_max_rank" VARCHAR(50),
    "event_max_rank_points" BIGINT,
    "event_rank" VARCHAR(50),
    "event_rank_points" BIGINT,
    "warmup_kills" BIGINT,
    "warmup_deaths" BIGINT,
    "warmup_wins" BIGINT,
    "warmup_losses" BIGINT,
    "warmup_abandons" BIGINT,
    "warmup_max_rank" VARCHAR(50),
    "warmup_max_rank_points" BIGINT,
    "warmup_rank" VARCHAR(50),
    "warmup_rank_points" BIGINT,
    "standard_kills" BIGINT,
    "standard_deaths" BIGINT,
    "standard_wins" BIGINT,
    "standard_losses" BIGINT,
    "standard_abandons" BIGINT,
    "standard_max_rank" VARCHAR(50),
    "standard_max_rank_points" BIGINT,
    "standard_rank" VARCHAR(50),
    "standard_rank_points" BIGINT,
    "ranked_kills" BIGINT,
    "ranked_deaths" BIGINT,
    "ranked_wins" BIGINT,
    "ranked_losses" BIGINT,
    "ranked_abandons" BIGINT,
    "ranked_max_rank" VARCHAR(50),
    "ranked_max_rank_points" BIGINT,
    "ranked_rank" VARCHAR(50),
    "ranked_rank_points" BIGINT,
    CONSTRAINT "uid_RankedStats_user_id_e8c803" UNIQUE ("user_id", "platform")
);
CREATE TABLE IF NOT EXISTS "Settings" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "emoji" TEXT,
    "default" TEXT,
    "valuetype" TEXT NOT NULL,
    "settingtype" TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS "GuildSettings" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "username" TEXT NOT NULL,
    "guildid" BIGINT NOT NULL,
    "value" TEXT NOT NULL,
    "valuetype" TEXT NOT NULL,
    "setting_id" BIGINT NOT NULL REFERENCES "Settings" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "UserSettings" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "username" TEXT NOT NULL,
    "userid" BIGINT NOT NULL,
    "value" TEXT NOT NULL,
    "valuetype" TEXT NOT NULL,
    "setting_id" BIGINT NOT NULL REFERENCES "Settings" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
