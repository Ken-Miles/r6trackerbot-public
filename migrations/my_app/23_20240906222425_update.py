from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "Commands" ADD "command_id" BIGINT;
        ALTER TABLE "Commands" ADD "transaction_id" UUID;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "Commands" DROP COLUMN "command_id";
        ALTER TABLE "Commands" DROP COLUMN "transaction_id";"""
