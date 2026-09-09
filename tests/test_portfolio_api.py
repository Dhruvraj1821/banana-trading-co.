import uuid

from httpx import AsyncClient, ASGITransport

from app.main import app


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def setup_user_and_card(client: AsyncClient):
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

    return trader_id, card_id


async def test_portfolio_reflects_holding_after_buy():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        trader_id, card_id = await setup_user_and_card(client)

        await client.post(
            "/trades/", json={"user_id": trader_id, "card_id": card_id, "side": "buy", "amount": 100}
        )

        response = await client.get(f"/users/{trader_id}/portfolio")
        assert response.status_code == 200
        data = response.json()
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["quantity"] > 0
        assert data["holdings"][0]["avg_cost_basis"] > 0


async def test_avg_cost_basis_is_weighted_average_across_two_buys():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        trader_id, card_id = await setup_user_and_card(client)

        first = await client.post(
            "/trades/", json={"user_id": trader_id, "card_id": card_id, "side": "buy", "amount": 100}
        )
        first_price = first.json()["price"]

        second = await client.post(
            "/trades/", json={"user_id": trader_id, "card_id": card_id, "side": "buy", "amount": 100}
        )
        second_price = second.json()["price"]

        portfolio = await client.get(f"/users/{trader_id}/portfolio")
        avg_cost_basis = portfolio.json()["holdings"][0]["avg_cost_basis"]

        # since price rises with each buy, the blended cost basis should
        # sit strictly between the two individual trade prices
        assert first_price < avg_cost_basis < second_price


async def test_portfolio_excludes_fully_sold_position():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        trader_id, card_id = await setup_user_and_card(client)

        buy_resp = await client.post(
            "/trades/", json={"user_id": trader_id, "card_id": card_id, "side": "buy", "amount": 100}
        )
        units = buy_resp.json()["quantity"]

        await client.post(
            "/trades/",
            json={"user_id": trader_id, "card_id": card_id, "side": "sell", "amount": units},
        )

        response = await client.get(f"/users/{trader_id}/portfolio")
        assert response.json()["holdings"] == []


async def test_portfolio_total_value_includes_balance_and_holdings():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        trader_id, card_id = await setup_user_and_card(client)

        await client.post(
            "/trades/", json={"user_id": trader_id, "card_id": card_id, "side": "buy", "amount": 100}
        )

        response = await client.get(f"/users/{trader_id}/portfolio")
        data = response.json()

        expected_total = data["currency_balance"] + data["holdings"][0]["market_value"]
        assert data["total_portfolio_value"] == expected_total