import uuid

from sqlalchemy import select
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import async_session_factory
from app.models import PriceHistory
from scripts.drift_worker import drift_one_card


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def get_price_history_for_card(card_id: str):
    async with async_session_factory() as session:
        result = await session.scalars(
            select(PriceHistory).where(PriceHistory.card_id == card_id)
        )
        return result.all()


async def test_buy_writes_a_trade_price_history_row():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_resp = await client.post("/users/", json={"username": unique_name("creator")})
        creator_id = creator_resp.json()["id"]

        card_resp = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
            },
        )
        card_id = card_resp.json()["id"]

        trader_resp = await client.post("/users/", json={"username": unique_name("trader")})
        trader_id = trader_resp.json()["id"]

        await client.post(
            "/trades/",
            json={"user_id": trader_id, "card_id": card_id, "side": "buy", "amount": 100},
        )

        rows = await get_price_history_for_card(card_id)
        assert len(rows) == 1
        assert rows[0].event == "trade"
        assert rows[0].price > 0


async def test_drift_writes_a_drift_price_history_row():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_resp = await client.post("/users/", json={"username": unique_name("creator")})
        creator_id = creator_resp.json()["id"]

        card_resp = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
            },
        )
        card_id = card_resp.json()["id"]

    await drift_one_card(card_id)

    rows = await get_price_history_for_card(card_id)
    assert len(rows) == 1
    assert rows[0].event == "drift"


async def test_multiple_trades_accumulate_separate_rows():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_resp = await client.post("/users/", json={"username": unique_name("creator")})
        creator_id = creator_resp.json()["id"]

        card_resp = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
            },
        )
        card_id = card_resp.json()["id"]

        trader_resp = await client.post("/users/", json={"username": unique_name("trader")})
        trader_id = trader_resp.json()["id"]

        for _ in range(3):
            await client.post(
                "/trades/",
                json={"user_id": trader_id, "card_id": card_id, "side": "buy", "amount": 50},
            )

        rows = await get_price_history_for_card(card_id)
        assert len(rows) == 3