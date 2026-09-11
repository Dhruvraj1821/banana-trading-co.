import uuid

from httpx import AsyncClient, ASGITransport

from app.main import app


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def create_test_user(client: AsyncClient) -> str:
    response = await client.post("/users/", json={"username": unique_name("user")})
    return response.json()["id"]


async def test_create_card():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_id = await create_test_user(client)
        response = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["price"] == 10.0


async def test_create_card_with_missing_creator_fails():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": "does-not-exist",
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
            },
        )

    assert response.status_code == 404


async def test_list_cards_includes_created_card():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_id = await create_test_user(client)
        card_name = unique_name("card")
        await client.post(
            "/cards/",
            json={
                "name": card_name,
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
            },
        )

        response = await client.get("/cards/")

    assert response.status_code == 200
    names = [card["name"] for card in response.json()]
    assert card_name in names


async def test_get_nonexistent_card_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/cards/does-not-exist")

    assert response.status_code == 404

async def test_create_card_with_creator_stake():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_id = await create_test_user(client)
        response = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
                "creator_stake_pct": 0.15,
            },
        )

    assert response.status_code == 201
    assert response.json()["creator_stake_pct"] == 0.15


async def test_create_card_with_stake_above_cap_fails():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_id = await create_test_user(client)
        response = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
                "creator_stake_pct": 0.5,
            },
        )

    assert response.status_code == 400


async def test_create_card_with_unlimited_supply_model_fails():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_id = await create_test_user(client)
        response = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
                "supply_model": "unlimited",
            },
        )

    assert response.status_code == 400


async def test_create_card_defaults_to_fixed_supply_zero_stake():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_id = await create_test_user(client)
        response = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
            },
        )

    data = response.json()
    assert data["supply_model"] == "fixed"
    assert data["creator_stake_pct"] == 0.0

async def test_create_card_grants_creator_stake_as_holding():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_id = await create_test_user(client)
        response = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
                "creator_stake_pct": 0.15,
            },
        )

        assert response.status_code == 201
        card = response.json()
        # 15% of 10000 total_supply = 1500 units carved out of the pool
        assert card["card_reserve"] == 8500.0

        portfolio_resp = await client.get(f"/users/{creator_id}/portfolio")
        holdings = portfolio_resp.json()["holdings"]
        assert len(holdings) == 1
        assert holdings[0]["quantity"] == 1500.0
        assert holdings[0]["avg_cost_basis"] == 0.0

async def test_create_card_with_stake_exceeding_pool_reserve_fails():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_id = await create_test_user(client)
        response = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                # only 500 units of pool depth, but 15% of 10000 = 1500 needed
                "initial_card_reserve": 500,
                "creator_stake_pct": 0.15,
            },
        )

    assert response.status_code == 400


async def test_create_card_with_zero_stake_grants_no_holding():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_id = await create_test_user(client)
        response = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 10000,
                "initial_currency_reserve": 100000,
                "initial_card_reserve": 10000,
            },
        )
        card = response.json()
        assert card["card_reserve"] == 10000.0

        portfolio_resp = await client.get(f"/users/{creator_id}/portfolio")
        assert portfolio_resp.json()["holdings"] == []