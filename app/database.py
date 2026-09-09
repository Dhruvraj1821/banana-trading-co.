from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):

    pass


engine = create_async_engine(settings.database_url, echo=False)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncSession:
    """
    A dependency for FastAPI routes: yields a session, then closes it
    automatically when the request is done, even if the request raised
    an error.
    """
    async with async_session_factory() as session:
        yield session