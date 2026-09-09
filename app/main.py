from fastapi import FastAPI

from app.routers import users

app = FastAPI(title="Banana Trading Company")

app.include_router(users.router)


@app.get("/health")
async def health():
    return {"status": "ok"}