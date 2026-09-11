import uuid

import pytest
from sqlalchemy import select, func
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import async_session_factory
from app.models import User, Card


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def total_currency_in_system() -> float:
    """Sums every user's balance plus every card's currency_reserve.
    This is the entire pool of currency that exists anywhere, if this
    number ever grows on its own, currency is being created from
    nothing somewhere."""
    async with async_session_factory() as session:
        user_total = await session.scalar(select(func.sum(User.currency_balance))) or 0.0
        card_total = await session.scalar(select(func.sum(Card.currency_reserve))) or 0.0
    return user_total + card_total


async def test_currency_only_decreases_by_burn_amount_across_many_trades():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_resp = await client.post("/users/", json={"username": unique_name("creator")})
        creator_id = creator_resp.json()["id"]

        card_resp = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 100000,
                "initial_currency_reserve": 1000000,
                "initial_card_reserve": 100000,
            },
        )
        card_id = card_resp.json()["id"]

        trader_ids = []
        for _ in range(5):
            resp = await client.post("/users/", json={"username": unique_name("trader")})
            trader_ids.append(resp.json()["id"])

        total_before = await total_currency_in_system()

        total_fee_amount = 0.0
        for trader_id in trader_ids:
            buy_resp = await client.post(
                "/trades/",
                json={"user_id": trader_id, "card_id": card_id, "side": "buy", "amount": 100},
            )
            total_fee_amount += buy_resp.json()["fee_amount"]
            units = buy_resp.json()["quantity"]

            sell_resp = await client.post(
                "/trades/",
                json={
                    "user_id": trader_id,
                    "card_id": card_id,
                    "side": "sell",
                    "amount": units / 2,
                },
            )
            total_fee_amount += sell_resp.json()["fee_amount"]

        total_after = await total_currency_in_system()

        default_burn_pct = 0.40  # FeeSplit's default burn_pct
        expected_total_burn = total_fee_amount * default_burn_pct

        assert (total_before - total_after) == pytest.approx(expected_total_burn, rel=1e-6)
        assert total_after < total_before