from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import users, cards, trades, websockets

app = FastAPI(title="Banana Trading Company")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(cards.router)
app.include_router(trades.router)
app.include_router(websockets.router)

@app.get("/health")
async def health():
    return {"status": "ok"}