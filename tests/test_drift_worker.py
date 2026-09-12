import json
import uuid

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.redis_client import redis_client
from scripts.drift_worker import drift_one_card


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def test_drift_one_card_changes_price_and_publishes():
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
        starting_price = card_resp.json()["price"]

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"card:{card_id}:price")
        await pubsub.get_message(timeout=1)

        new_price = await drift_one_card(card_id)

        assert new_price is not None
        # drift is clamped to a few percent per tick by design
        assert abs(new_price - starting_price) / starting_price < 0.05

        message = await pubsub.get_message(timeout=2)
        assert message is not None
        payload = json.loads(message["data"])
        assert payload["event"] == "drift"
        assert payload["card_id"] == card_id

        await pubsub.unsubscribe(f"card:{card_id}:price")
        await pubsub.aclose()


async def test_drift_one_card_returns_none_for_nonexistent_card():
    result = await drift_one_card("does-not-exist")
    assert result is None