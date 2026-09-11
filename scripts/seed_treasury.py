import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models import User
from app.constants import TREASURY_USERNAME


async def main():
    async with async_session_factory() as session:
        existing = await session.scalar(
            select(User).where(User.username == TREASURY_USERNAME)
        )
        if existing is not None:
            print(f"Treasury account already exists: {existing.id}")
            return

        treasury = User(username=TREASURY_USERNAME, currency_balance=0.0)
        session.add(treasury)
        await session.commit()
        await session.refresh(treasury)
        print(f"Created treasury account: {treasury.id}")


if __name__ == "__main__":
    asyncio.run(main())