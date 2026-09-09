import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        print("Connected successfully. SELECT 1 returned:", result.scalar())
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())