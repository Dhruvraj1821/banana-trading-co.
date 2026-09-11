import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def setup_user_and_card(client: AsyncClient, cap_pct: float = 0.20):
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

async def test_buy_updates_balance_and_price():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user_id, card_id = await setup_user_and_card(client)

        trade_resp = await client.post(
            "/trades/", json={"user_id": user_id, "card_id": card_id, "side": "buy", "amount": 100}
        )
        assert trade_resp.status_code == 201
        trade = trade_resp.json()
        assert trade["side"] == "buy"
        assert trade["quantity"] > 0

        user_resp = await client.get(f"/users/{user_id}")
        assert user_resp.json()["currency_balance"] == 900.0

        card_resp = await client.get(f"/cards/{card_id}")
        assert card_resp.json()["price"] > 10.0  # price rose after a buy


async def test_sell_updates_balance_and_holding():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user_id, card_id = await setup_user_and_card(client)

        buy_resp = await client.post(
            "/trades/", json={"user_id": user_id, "card_id": card_id, "side": "buy", "amount": 100}
        )
        units_bought = buy_resp.json()["quantity"]

        sell_resp = await client.post(
            "/trades/",
            json={"user_id": user_id, "card_id": card_id, "side": "sell", "amount": units_bought},
        )
        assert sell_resp.status_code == 201

        user_resp = await client.get(f"/users/{user_id}")
        # spent 100, sold back for less than 100 due to fees + slippage
        assert user_resp.json()["currency_balance"] < 1000.0


async def test_buy_with_insufficient_balance_fails():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user_id, card_id = await setup_user_and_card(client)

        response = await client.post(
            "/trades/",
            json={"user_id": user_id, "card_id": card_id, "side": "buy", "amount": 5000},
        )
        assert response.status_code == 400


async def test_sell_with_insufficient_holdings_fails():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user_id, card_id = await setup_user_and_card(client)

        response = await client.post(
            "/trades/",
            json={"user_id": user_id, "card_id": card_id, "side": "sell", "amount": 50},
        )
        assert response.status_code == 400


async def test_buy_exceeding_ownership_cap_fails():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_resp = await client.post("/users/", json={"username": unique_name("creator")})
        creator_id = creator_resp.json()["id"]

        # Small pool relative to a 1000-currency budget: total_supply=100,
        # default cap_pct=0.20 means the cap is 20 units, easily reachable
        # with a large-but-affordable single trade.
        card_resp = await client.post(
            "/cards/",
            json={
                "name": unique_name("card"),
                "creator_id": creator_id,
                "total_supply": 100,
                "initial_currency_reserve": 1000,
                "initial_card_reserve": 100,
            },
        )
        card_id = card_resp.json()["id"]

        buyer_resp = await client.post("/users/", json={"username": unique_name("buyer")})
        buyer_id = buyer_resp.json()["id"]

        response = await client.post(
            "/trades/",
            json={"user_id": buyer_id, "card_id": card_id, "side": "buy", "amount": 900},
        )
        assert response.status_code == 400
        assert "cap" in response.json()["detail"].lower()

async def test_buy_credits_creator_and_treasury_fees():
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

        creator_balance_before = (await client.get(f"/users/{creator_id}")).json()["currency_balance"]

        trade_resp = await client.post(
            "/trades/", json={"user_id": trader_id, "card_id": card_id, "side": "buy", "amount": 100}
        )
        fee_amount = trade_resp.json()["fee_amount"]

        creator_balance_after = (await client.get(f"/users/{creator_id}")).json()["currency_balance"]

        # default FeeSplit is 30% creator / 40% burn / 30% treasury
        expected_creator_fee = fee_amount * 0.30
        assert creator_balance_after - creator_balance_before == pytest.approx(expected_creator_fee)


async def test_creator_trading_their_own_card_does_not_deadlock_or_double_lock():
    """The creator and trader are the same user here, exercising the
    dedup in the lock-ordering logic."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creator_resp = await client.post("/users/", json={"username": unique_name("selftrader")})
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

        response = await client.post(
            "/trades/", json={"user_id": creator_id, "card_id": card_id, "side": "buy", "amount": 100}
        )
        assert response.status_code == 201

async def test_creator_stake_at_cap_blocks_further_buying():
    """A creator who took the max allowed stake (20%) already owns as
    much of the card as the anti-whale cap permits. No special
    treatment: any further buy is blocked exactly like a whale's would be."""
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
                "creator_stake_pct": 0.20,
            },
        )
        card_id = card_resp.json()["id"]

        response = await client.post(
            "/trades/", json={"user_id": creator_id, "card_id": card_id, "side": "buy", "amount": 10}
        )
        assert response.status_code == 400
        assert "cap" in response.json()["detail"].lower()


async def test_creator_selling_stake_faces_same_slippage_as_anyone_else():
    """Selling the creator stake goes through the same AMM math as any
    holder's sale, no fixed-price redemption or special exit path."""
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
                "creator_stake_pct": 0.20,
            },
        )
        card_id = card_resp.json()["id"]
        starting_price = card_resp.json()["price"]

        portfolio = await client.get(f"/users/{creator_id}/portfolio")
        stake_units = portfolio.json()["holdings"][0]["quantity"]

        sell_resp = await client.post(
            "/trades/",
            json={"user_id": creator_id, "card_id": card_id, "side": "sell", "amount": stake_units},
        )
        assert sell_resp.status_code == 201

        new_card = (await client.get(f"/cards/{card_id}")).json()
        assert new_card["price"] < starting_price