from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "RankedStatsV2" ADD "api_last_updated" TIMESTAMPTZ;
        ALTER TABLE "RankedStatsV2" ADD "is_overwolf_app_user" BOOL NOT NULL  DEFAULT False;
        ALTER TABLE "RankedStatsV2" ADD "battlepass_level" BIGINT;
        ALTER TABLE "RankedStatsV2" ADD "clearance_level" BIGINT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "RankedStatsV2" DROP COLUMN "api_last_updated";
        ALTER TABLE "RankedStatsV2" DROP COLUMN "is_overwolf_app_user";
        ALTER TABLE "RankedStatsV2" DROP COLUMN "battlepass_level";
        ALTER TABLE "RankedStatsV2" DROP COLUMN "clearance_level";"""
