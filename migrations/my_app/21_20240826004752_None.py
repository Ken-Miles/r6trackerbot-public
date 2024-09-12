from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "Alerts" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "alert_title" VARCHAR(100) NOT NULL,
    "alert_message" TEXT NOT NULL,
    "alert_type" VARCHAR(100) NOT NULL,
    "is_active" BOOL NOT NULL  DEFAULT True
);
CREATE TABLE IF NOT EXISTS "AlertViewings" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL,
    "alert_id" BIGINT NOT NULL REFERENCES "Alerts" ("id") ON DELETE CASCADE
);
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
CREATE TABLE IF NOT EXISTS "Blacklist" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "offender_id" BIGINT NOT NULL,
    "offender_name" VARCHAR(100),
    "reason" VARCHAR(255),
    "timestamp" TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS "CommandInvocation" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "transaction_id" UUID,
    "command_id" BIGINT NOT NULL,
    "prefix" VARCHAR(25),
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
    "prefix" VARCHAR(23) NOT NULL,
    "command" VARCHAR(100) NOT NULL,
    "failed" BOOL NOT NULL  DEFAULT False,
    "app_command" BOOL NOT NULL  DEFAULT False,
    "args" JSONB,
    "kwargs" JSONB
);
CREATE TABLE IF NOT EXISTS "Matches" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "match_id" UUID NOT NULL UNIQUE,
    "gamemode" VARCHAR(50) NOT NULL,
    "datacenter" VARCHAR(50),
    "timestamp" TIMESTAMPTZ NOT NULL,
    "gamemode_name" VARCHAR(50) NOT NULL,
    "has_overwolf_roster" BOOL NOT NULL  DEFAULT False,
    "has_session_data" BOOL NOT NULL  DEFAULT False,
    "is_rollback" BOOL NOT NULL  DEFAULT False,
    "_raw" JSONB
);
COMMENT ON TABLE "Matches" IS 'Represents a match in Rainbow Six Siege.';
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
    "name" VARCHAR(100),
    "platform" VARCHAR(100) NOT NULL  DEFAULT 'uplay'
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
CREATE TABLE IF NOT EXISTS "R6UserConnections" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "userid" VARCHAR(100) NOT NULL,
    "name" VARCHAR(100),
    "platform" VARCHAR(100) NOT NULL,
    "platform_id" VARCHAR(100),
    "request_id" UUID,
    "pfp_url" VARCHAR(255),
    "pfp_url_last_updated" TIMESTAMPTZ,
    "is_third_party" BOOL NOT NULL  DEFAULT False,
    "manual" BOOL NOT NULL  DEFAULT False,
    "linked_by" BIGINT,
    "profile_id" BIGINT NOT NULL REFERENCES "R6User" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "MatchSegments" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "platform_family" VARCHAR(10),
    "result" VARCHAR(10),
    "status" VARCHAR(20),
    "has_extra_stats" BOOL NOT NULL  DEFAULT False,
    "matches_played" BIGINT NOT NULL  DEFAULT 1,
    "wins" BIGINT   DEFAULT 0,
    "losses" BIGINT   DEFAULT 0,
    "abandons" BIGINT   DEFAULT 0,
    "kills" BIGINT   DEFAULT 0,
    "deaths" BIGINT   DEFAULT 0,
    "rank" BIGINT,
    "rank_points" BIGINT,
    "top_rank_position" BIGINT,
    "rank_points_delta" BIGINT,
    "rank_previous" BIGINT,
    "top_rank_position_previous" BIGINT,
    "kd_ratio" DOUBLE PRECISION,
    "win_percent" DOUBLE PRECISION,
    "kills_per_minute" DOUBLE PRECISION,
    "damage_done" BIGINT,
    "match_score" BIGINT,
    "playtime" BIGINT,
    "extra_data" JSONB,
    "_raw" JSONB,
    "match_id" BIGINT NOT NULL REFERENCES "Matches" ("id") ON DELETE CASCADE,
    "platform_connection_id" BIGINT NOT NULL REFERENCES "R6UserConnections" ("id") ON DELETE CASCADE,
    "user_id" BIGINT NOT NULL REFERENCES "R6User" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "MatchSegments" IS 'This model stores player-specific information to a match, such as K/D, performance, etc';
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
CREATE TABLE IF NOT EXISTS "playerencounters" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "count" BIGINT NOT NULL,
    "rank" BIGINT NOT NULL,
    "is_banned" BOOL NOT NULL  DEFAULT False,
    "lastest_match" TIMESTAMPTZ NOT NULL,
    "season_num" INT NOT NULL,
    "encountered_player_id" BIGINT NOT NULL REFERENCES "R6UserConnections" ("id") ON DELETE CASCADE,
    "encountering_player_id" BIGINT NOT NULL REFERENCES "R6UserConnections" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "RankedStats" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "platform" VARCHAR(100) NOT NULL,
    "request_id" UUID,
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
    "season_number" VARCHAR(6) NOT NULL  DEFAULT 'Y9S2',
    "user_id" BIGINT NOT NULL REFERENCES "R6User" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_RankedStats_user_id_e8c803" UNIQUE ("user_id", "platform")
);
CREATE TABLE IF NOT EXISTS "RankedStatsV2" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "api_last_updated" TIMESTAMPTZ,
    "expiry_date" TIMESTAMPTZ,
    "battlepass_level" BIGINT,
    "clearance_level" BIGINT,
    "is_overwolf_app_user" BOOL NOT NULL  DEFAULT False,
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
CREATE TABLE IF NOT EXISTS "ReportedErrors" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "error_id" UUID NOT NULL,
    "user_id" BIGINT NOT NULL,
    "forum_id" BIGINT NOT NULL,
    "forum_post_id" BIGINT NOT NULL,
    "forum_initial_message_id" BIGINT NOT NULL,
    "error_message" TEXT,
    "resolved" BOOL NOT NULL  DEFAULT False
);
COMMENT ON TABLE "ReportedErrors" IS 'Errors Reported to my private forum via that menu thing.';
CREATE TABLE IF NOT EXISTS "SavedMessages" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(100) NOT NULL,
    "guild_id" BIGINT,
    "channel_id" BIGINT NOT NULL,
    "message_id" BIGINT NOT NULL,
    "author_id" BIGINT NOT NULL,
    "author_name" VARCHAR(100)
);
COMMENT ON TABLE "SavedMessages" IS 'Messages that the bot has saved for later use.';
CREATE TABLE IF NOT EXISTS "Settings" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL UNIQUE,
    "username" VARCHAR(100) NOT NULL,
    "preferred_platform" VARCHAR(5) NOT NULL  DEFAULT 'N/A',
    "show_on_leaderboard" BOOL NOT NULL  DEFAULT True,
    "prefix" VARCHAR(5) NOT NULL  DEFAULT '!',
    "use_custom_prefix" BOOL NOT NULL  DEFAULT False,
    "show_prefix_command_tips" BOOL NOT NULL  DEFAULT True,
    "language" VARCHAR(5) NOT NULL  DEFAULT 'en',
    "timezone" VARCHAR(50) NOT NULL  DEFAULT 'UTC',
    "color" VARCHAR(7) NOT NULL  DEFAULT '#7289DA'
);
CREATE TABLE IF NOT EXISTS "SettingsInfo" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(100) NOT NULL,
    "description" VARCHAR(100) NOT NULL,
    "valuetype" VARCHAR(100) NOT NULL,
    "emoji" VARCHAR(100),
    "min_value" INT,
    "max_value" INT,
    "active" BOOL NOT NULL  DEFAULT True
);
CREATE TABLE IF NOT EXISTS "Tournaments" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(100) NOT NULL,
    "description" TEXT,
    "team_size" INT,
    "author_id" BIGINT NOT NULL,
    "author_name" VARCHAR(100),
    "max_teams" INT NOT NULL  DEFAULT -1,
    "random_teams" BOOL NOT NULL  DEFAULT False,
    "current_participants" INT NOT NULL  DEFAULT 0,
    "ended" BOOL NOT NULL  DEFAULT False
);
COMMENT ON TABLE "Tournaments" IS 'Toxic Tourneys';
CREATE TABLE IF NOT EXISTS "TourneyTeams" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(100) NOT NULL,
    "description" TEXT,
    "tournament_id" BIGINT NOT NULL REFERENCES "Tournaments" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "TourneyParticipants" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "is_team_leader" BOOL NOT NULL  DEFAULT False,
    "user_id" BIGINT NOT NULL,
    "team_id" BIGINT REFERENCES "TourneyTeams" ("id") ON DELETE CASCADE,
    "tournament_id" BIGINT NOT NULL REFERENCES "Tournaments" ("id") ON DELETE CASCADE,
    "user_connection_id" BIGINT NOT NULL REFERENCES "R6UserConnections" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "TourneyParticipants" IS 'Participants in a tournament.';
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
