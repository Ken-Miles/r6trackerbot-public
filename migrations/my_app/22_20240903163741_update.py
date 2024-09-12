from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "Blacklist" ADD "type" VARCHAR(10) NOT NULL  DEFAULT 'user';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "Blacklist" DROP COLUMN "type";"""
