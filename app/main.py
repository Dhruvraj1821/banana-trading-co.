from fastapi import FastAPI

from app.routers import users, cards, trades

app = FastAPI(title="Banana Trading Company")

app.include_router(users.router)
app.include_router(cards.router)
app.include_router(trades.router)

@app.get("/health")
async def health():
    return {"status": "ok"}