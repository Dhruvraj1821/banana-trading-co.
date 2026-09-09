import asyncio
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def test_concurrent_buys_on_same_card_have_no_lost_updates():
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
        starting_card_reserve = card_resp.json()["card_reserve"]

        num_traders = 10
        trade_amount = 50

        user_ids = []
        for _ in range(num_traders):
            resp = await client.post("/users/", json={"username": unique_name("trader")})
            user_ids.append(resp.json()["id"])

        async def do_buy(user_id: str):
            return await client.post(
                "/trades/",
                json={
                    "user_id": user_id,
                    "card_id": card_id,
                    "side": "buy",
                    "amount": trade_amount,
                },
            )

        # Fire all 10 buys at the exact same moment, not one after another.
        responses = await asyncio.gather(*[do_buy(uid) for uid in user_ids])

        assert all(r.status_code == 201 for r in responses)

        total_units_acquired = sum(r.json()["quantity"] for r in responses)

        final_card = (await client.get(f"/cards/{card_id}")).json()
        actual_reserve_depleted = starting_card_reserve - final_card["card_reserve"]

        assert total_units_acquired == pytest.approx(actual_reserve_depleted, rel=1e-6)


async def test_concurrent_trades_on_different_cards_all_succeed_independently():
    """Sanity check on the earlier UX discussion: trades on different
    cards shouldn't block or interfere with each other at all."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_resp = await client.post("/users/", json={"username": unique_name("creator")})
        creator_id = creator_resp.json()["id"]

        card_ids = []
        for _ in range(5):
            resp = await client.post(
                "/cards/",
                json={
                    "name": unique_name("card"),
                    "creator_id": creator_id,
                    "total_supply": 10000,
                    "initial_currency_reserve": 100000,
                    "initial_card_reserve": 10000,
                },
            )
            card_ids.append(resp.json()["id"])

        user_ids = []
        for _ in range(5):
            resp = await client.post("/users/", json={"username": unique_name("trader")})
            user_ids.append(resp.json()["id"])

        async def do_buy(user_id: str, card_id: str):
            return await client.post(
                "/trades/",
                json={"user_id": user_id, "card_id": card_id, "side": "buy", "amount": 50},
            )

        responses = await asyncio.gather(
            *[do_buy(uid, cid) for uid, cid in zip(user_ids, card_ids)]
        )

        assert all(r.status_code == 201 for r in responses)