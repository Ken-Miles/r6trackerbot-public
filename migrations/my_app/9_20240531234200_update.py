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
        CREATE TABLE IF NOT EXISTS "Commands" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "guild_id" BIGINT,
    "channel_id" BIGINT,
    "author_id" BIGINT NOT NULL,
    "used" TIMESTAMPTZ NOT NULL,
    "prefix" VARCHAR(20) NOT NULL,
    "command" VARCHAR(100) NOT NULL,
    "failed" BOOL NOT NULL  DEFAULT False,
    "app_command" BOOL NOT NULL  DEFAULT False,
    "args" JSONB,
    "kwargs" JSONB
);
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
        DROP TABLE IF EXISTS "Blacklist";
        DROP TABLE IF EXISTS "Commands";
        DROP TABLE IF EXISTS "Votes";
        DROP TABLE IF EXISTS "WebhookAuthorization";"""
