import json
import uuid

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.redis_client import redis_client


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def test_buy_publishes_price_update_to_redis():
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

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"card:{card_id}:price")
        # the subscribe call itself generates a confirmation message;
        # drain it so it doesn't get mistaken for the real payload
        await pubsub.get_message(timeout=1)

        await client.post(
            "/trades/",
            json={"user_id": trader_id, "card_id": card_id, "side": "buy", "amount": 100},
        )

        message = await pubsub.get_message(timeout=2)
        assert message is not None
        payload = json.loads(message["data"])
        assert payload["card_id"] == card_id
        assert payload["event"] == "trade"
        assert payload["price"] > 0

        await pubsub.unsubscribe(f"card:{card_id}:price")
        await pubsub.aclose()