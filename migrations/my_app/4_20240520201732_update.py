from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "RankedStats" ADD "season_number" VARCHAR(6) NOT NULL  DEFAULT 'Y9S1';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "RankedStats" DROP COLUMN "season_number";"""
