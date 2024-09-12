from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "Alerts" ALTER COLUMN "alert_type" DROP NOT NULL;
        ALTER TABLE "RankedStats" ALTER COLUMN "season_number" SET DEFAULT 'Y9S3';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "Alerts" ALTER COLUMN "alert_type" SET NOT NULL;
        ALTER TABLE "RankedStats" ALTER COLUMN "season_number" SET DEFAULT 'Y9S2';"""
