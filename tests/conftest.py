import pytest
from sqlalchemy import select

from app.database import async_session_factory
from app.models import User
from app.constants import TREASURY_USERNAME


@pytest.fixture(scope="session", autouse=True)
async def ensure_treasury_account():
    async with async_session_factory() as session:
        existing = await session.scalar(
            select(User).where(User.username == TREASURY_USERNAME)
        )
        if existing is None:
            treasury = User(username=TREASURY_USERNAME, currency_balance=0.0)
            session.add(treasury)
            await session.commit()