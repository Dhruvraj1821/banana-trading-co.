import asyncio
import sys

import websockets


async def listen(card_id: str):
    uri = f"ws://localhost:8000/ws/cards/{card_id}"
    async with websockets.connect(uri) as ws:
        print(f"Connected, listening for price updates on card {card_id}...")
        async for message in ws:
            print("Received:", message)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.test_ws_client <card_id>")
        sys.exit(1)
    asyncio.run(listen(sys.argv[1]))