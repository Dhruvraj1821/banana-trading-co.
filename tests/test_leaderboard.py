import uuid

from httpx import AsyncClient, ASGITransport

from app.main import app


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def test_networth_leaderboard_is_sorted_descending():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/users/", json={"username": unique_name("user")})
        response = await client.get("/leaderboard/networth")

    assert response.status_code == 200
    net_worths = [entry["net_worth"] for entry in response.json()]
    assert net_worths == sorted(net_worths, reverse=True)


async def test_roi_leaderboard_is_sorted_descending():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/leaderboard/roi")

    rois = [entry["roi_pct"] for entry in response.json()]
    assert rois == sorted(rois, reverse=True)


async def test_fresh_user_has_zero_roi_and_starting_net_worth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user_resp = await client.post("/users/", json={"username": unique_name("fresh")})
        user_id = user_resp.json()["id"]

        response = await client.get("/leaderboard/networth")
        entry = next(e for e in response.json() if e["user_id"] == user_id)

        assert entry["net_worth"] == 1000.0
        assert entry["roi_pct"] == 0.0


async def test_treasury_account_excluded_from_leaderboard():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/leaderboard/networth")

    usernames = [entry["username"] for entry in response.json()]
    assert "SYSTEM_TREASURY" not in usernames


async def test_creator_appears_on_creators_leaderboard_after_a_trade():
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

        response = await client.get("/leaderboard/creators")
        entry = next(e for e in response.json() if e["user_id"] == creator_id)

        assert entry["card_count"] == 1
        assert entry["total_trading_volume"] > 0


async def test_user_with_no_cards_absent_from_creators_leaderboard():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user_resp = await client.post("/users/", json={"username": unique_name("noncreator")})
        user_id = user_resp.json()["id"]

        response = await client.get("/leaderboard/creators")

    user_ids = [e["user_id"] for e in response.json()]
    assert user_id not in user_ids