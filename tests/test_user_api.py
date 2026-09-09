import uuid

from httpx import AsyncClient, ASGITransport

from app.main import app


def unique_username(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def test_create_user():
    transport = ASGITransport(app=app)
    username = unique_username("alice")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/users/", json={"username": username})

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == username
    assert data["currency_balance"] == 1000.0


async def test_create_duplicate_user_fails():
    transport = ASGITransport(app=app)
    username = unique_username("alice")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/users/", json={"username": username})
        response = await client.post("/users/", json={"username": username})

    assert response.status_code == 409


async def test_get_nonexistent_user_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/users/does-not-exist")

    assert response.status_code == 404