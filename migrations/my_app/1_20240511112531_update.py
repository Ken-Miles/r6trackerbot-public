from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "R6UserConnections" ADD "pfp_url_last_updated" TIMESTAMPTZ;
        ALTER TABLE "R6UserConnections" ADD "pfp_url" VARCHAR(255);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "R6UserConnections" DROP COLUMN "pfp_url_last_updated";
        ALTER TABLE "R6UserConnections" DROP COLUMN "pfp_url";"""
