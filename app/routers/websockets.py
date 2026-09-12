import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.redis_client import redis_client

router = APIRouter(tags=["websockets"])


@router.websocket("/ws/cards/{card_id}")
async def card_price_stream(websocket: WebSocket, card_id: str):
    await websocket.accept()

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"card:{card_id}:price")

    # Confirm to the client that the subscription is actually live,
    # closing the race where a trade published before this point would
    # otherwise be silently missed.
    await websocket.send_text(json.dumps({"event": "subscribed", "card_id": card_id}))

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            if message is not None:
                await websocket.send_text(message["data"])
            else:
                await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"card:{card_id}:price")
        await pubsub.aclose()