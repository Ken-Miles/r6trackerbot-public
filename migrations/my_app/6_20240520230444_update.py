from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "SettingsInfo" ALTER COLUMN "description" TYPE VARCHAR(100) USING "description"::VARCHAR(100);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "SettingsInfo" ALTER COLUMN "description" TYPE TEXT USING "description"::TEXT;"""
