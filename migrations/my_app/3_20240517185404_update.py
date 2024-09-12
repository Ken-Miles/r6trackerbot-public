from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "R6UserConnections" ADD "linked_by" BIGINT;
        ALTER TABLE "R6UserConnections" ADD "manual" BOOL NOT NULL  DEFAULT False;
        ALTER TABLE "RankedStats" ALTER COLUMN "user_id" TYPE BIGINT USING "user_id"::BIGINT;
        ALTER TABLE "RankedStats" ADD CONSTRAINT "fk_RankedSt_R6User_c5cd95a0" FOREIGN KEY ("user_id") REFERENCES "R6User" ("id") ON DELETE CASCADE;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "RankedStats" DROP CONSTRAINT "fk_RankedSt_R6User_c5cd95a0";
        ALTER TABLE "RankedStats" DROP COLUMN "request_id";
        ALTER TABLE "R6UserConnections" DROP COLUMN "linked_by";
        ALTER TABLE "R6UserConnections" DROP COLUMN "manual";"""
