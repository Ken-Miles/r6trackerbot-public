from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "Blacklist" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "offender_id" BIGINT NOT NULL,
    "offernder_name" VARCHAR(100),
    "reason" VARCHAR(255),
    "timestamp" TIMESTAMPTZ NOT NULL
);
        CREATE TABLE IF NOT EXISTS "CommandInvocation" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "command_id" BIGINT NOT NULL UNIQUE,
    "prefix" VARCHAR(20),
    "is_slash" BOOL NOT NULL  DEFAULT False,
    "user_id" BIGINT NOT NULL,
    "guild_id" BIGINT,
    "channel_id" BIGINT,
    "command" VARCHAR(100) NOT NULL,
    "args" JSONB NOT NULL,
    "kwargs" JSONB NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    "completed" BOOL,
    "completion_timestamp" TIMESTAMPTZ,
    "error" VARCHAR(255)
);
        CREATE TABLE IF NOT EXISTS "Commands" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "guild_id" BIGINT,
    "channel_id" BIGINT,
    "author_id" BIGINT NOT NULL,
    "used" TIMESTAMPTZ NOT NULL,
    "uses" BIGINT NOT NULL  DEFAULT 1,
    "prefix" VARCHAR(20) NOT NULL,
    "command" VARCHAR(100) NOT NULL,
    "failed" BOOL NOT NULL  DEFAULT False,
    "app_command" BOOL NOT NULL  DEFAULT False,
    "args" JSONB,
    "kwargs" JSONB
);
        CREATE TABLE IF NOT EXISTS "NameChanges" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(100) NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    "user_id" BIGINT NOT NULL REFERENCES "R6User" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "NameChanges" IS 'This model is used to store name changes of a user.';
        CREATE TABLE IF NOT EXISTS "pastrankedpoints" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "date" TIMESTAMPTZ NOT NULL,
    "rank_points" BIGINT NOT NULL  DEFAULT 1000,
    "rank_name" VARCHAR(50) NOT NULL,
    "_raw" JSONB,
    "user_connection_id" BIGINT NOT NULL REFERENCES "R6UserConnections" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "pastrankedpoints" IS 'This model is similar to RankedStatsV2, but this only shows ranked stats current and past.';
        ALTER TABLE "R6UserConnections" ADD "request_id" UUID;
        ALTER TABLE "R6UserConnections" ALTER COLUMN "platform_id" DROP NOT NULL;
        ALTER TABLE "R6UserConnections" ALTER COLUMN "profile_id" TYPE BIGINT USING "profile_id"::BIGINT;
        ALTER TABLE "RankedStats" ALTER COLUMN "user_id" TYPE BIGINT USING "user_id"::BIGINT;
        CREATE TABLE IF NOT EXISTS "RankedStatsSeasonal" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "expiry_date" TIMESTAMPTZ,
    "season" INT NOT NULL,
    "season_name" VARCHAR(50) NOT NULL,
    "season_short" VARCHAR(5) NOT NULL,
    "season_color" VARCHAR(20) NOT NULL,
    "gamemode" VARCHAR(50) NOT NULL,
    "gamemode_name" VARCHAR(50) NOT NULL,
    "kills" BIGINT,
    "deaths" BIGINT,
    "kdratio" DOUBLE PRECISION,
    "killspergame" DOUBLE PRECISION,
    "matchesplayed" BIGINT,
    "matcheswon" BIGINT,
    "matcheslost" BIGINT,
    "matchesabandoned" BIGINT,
    "winpercentage" DOUBLE PRECISION,
    "rankpoints" BIGINT,
    "maxrankpoints" BIGINT,
    "_raw" JSONB,
    "platform_connection_id" BIGINT NOT NULL REFERENCES "R6UserConnections" ("id") ON DELETE CASCADE,
    "ranked_stats_id" BIGINT REFERENCES "RankedStatsV2" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "RankedStatsSeasonal" IS 'Season specific stats for a user.';
        CREATE TABLE IF NOT EXISTS "RankedStatsV2" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "expiry_date" TIMESTAMPTZ,
    "overview_matchesplayed" BIGINT,
    "overview_matcheswon" BIGINT,
    "overview_matcheslost" BIGINT,
    "overview_matchesabandoned" BIGINT,
    "overview_timeplayed" BIGINT,
    "overview_kills" BIGINT,
    "overview_deaths" BIGINT,
    "overview_attacker_roundswon" BIGINT,
    "overview_attacker_teamkillsinobj" BIGINT,
    "overview_attacker_enemykillsinobj" BIGINT,
    "overview_attacker_teamkillsoutobj" BIGINT,
    "overview_defender_roundswon" BIGINT,
    "overview_defender_teamkillsinobj" BIGINT,
    "overview_defender_enemykillsinobj" BIGINT,
    "overview_defender_teamkillsoutobj" BIGINT,
    "overview_defender_enemykillsoutobj" BIGINT,
    "overview_headshots" BIGINT,
    "overview_headshotsmissed" BIGINT,
    "overview_headshotpercentage" DOUBLE PRECISION,
    "overview_wallbangs" BIGINT,
    "overview_damagedealt" BIGINT,
    "overview_assists" BIGINT,
    "overview_teamkills" BIGINT,
    "overview_playstyle_attacker_breacher" BIGINT,
    "overview_playstyle_attacker_entryfragger" BIGINT,
    "overview_playstyle_attacker_intelprovider" BIGINT,
    "overview_playstyle_attacker_roamclearer" BIGINT,
    "overview_playstyle_attacker_supporter" BIGINT,
    "overview_playstyle_attacker_utilityclearer" BIGINT,
    "overview_playstyle_defender_debuffer" BIGINT,
    "overview_playstyle_defender_entrydenier" BIGINT,
    "overview_playstyle_defender_intelprovider" BIGINT,
    "overview_playstyle_defender_supporter" BIGINT,
    "overview_playstyle_defender_trapper" BIGINT,
    "overview_playstyle_defender_utilitydenier" BIGINT,
    "overview_kdratio" DOUBLE PRECISION,
    "overview_killspermatch" DOUBLE PRECISION,
    "overview_killspermin" DOUBLE PRECISION,
    "overview_winpercentage" DOUBLE PRECISION,
    "overview_timealive" BIGINT,
    "ranked_matchesplayed" BIGINT,
    "ranked_matcheswon" BIGINT,
    "ranked_matcheslost" BIGINT,
    "ranked_matchesabandoned" BIGINT,
    "ranked_timeplayed" BIGINT,
    "ranked_kills" BIGINT,
    "ranked_deaths" BIGINT,
    "ranked_kdratio" DOUBLE PRECISION,
    "ranked_killspermatch" DOUBLE PRECISION,
    "ranked_winpercentage" DOUBLE PRECISION,
    "event_matchesplayed" BIGINT,
    "event_matcheswon" BIGINT,
    "event_matcheslost" BIGINT,
    "event_abandoned" BIGINT,
    "event_timeplayed" BIGINT,
    "event_kills" BIGINT,
    "event_deaths" BIGINT,
    "event_kdratio" DOUBLE PRECISION,
    "event_killspermatch" DOUBLE PRECISION,
    "event_winpercentage" DOUBLE PRECISION,
    "quickplay_matchesplayed" BIGINT,
    "quickplay_matcheswon" BIGINT,
    "quickplay_matcheslost" BIGINT,
    "quickplay_abandoned" BIGINT,
    "quickplay_timeplayed" BIGINT,
    "quickplay_kills" BIGINT,
    "quickplay_deaths" BIGINT,
    "quickplay_kdratio" DOUBLE PRECISION,
    "quickplay_killspermatch" DOUBLE PRECISION,
    "quickplay_winpercentage" DOUBLE PRECISION,
    "_raw" JSONB,
    "trackergg_connection_id" BIGINT REFERENCES "R6UserConnections" ("id") ON DELETE CASCADE,
    "user_id" BIGINT REFERENCES "R6User" ("id") ON DELETE CASCADE,
    "user_connection_id" BIGINT NOT NULL REFERENCES "R6UserConnections" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "RankedStatsV2" IS 'This class is a new one to start new stats tracking for the new ranking provider (TrackerNetwork).';
        CREATE TABLE IF NOT EXISTS "Votes" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL,
    "username" VARCHAR(100),
    "avatar" TEXT,
    "site" VARCHAR(255) NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    "loggedby" VARCHAR(100) NOT NULL,
    "is_weekend" BOOL NOT NULL  DEFAULT False,
    "addl_data" JSONB,
    "_raw" JSONB
);
        CREATE TABLE IF NOT EXISTS "WebhookAuthorization" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "site" VARCHAR(100) NOT NULL,
    "authorization" VARCHAR(255) NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "RankedStats" ALTER COLUMN "user_id" TYPE BIGINT USING "user_id"::BIGINT;
        ALTER TABLE "R6UserConnections" DROP COLUMN "request_id";
        ALTER TABLE "R6UserConnections" ALTER COLUMN "platform_id" SET NOT NULL;
        ALTER TABLE "R6UserConnections" ALTER COLUMN "profile_id" TYPE BIGINT USING "profile_id"::BIGINT;
        DROP TABLE IF EXISTS "Blacklist";
        DROP TABLE IF EXISTS "CommandInvocation";
        DROP TABLE IF EXISTS "Commands";
        DROP TABLE IF EXISTS "NameChanges";
        DROP TABLE IF EXISTS "pastrankedpoints";
        DROP TABLE IF EXISTS "RankedStatsSeasonal";
        DROP TABLE IF EXISTS "RankedStatsV2";
        DROP TABLE IF EXISTS "Votes";
        DROP TABLE IF EXISTS "WebhookAuthorization";"""
