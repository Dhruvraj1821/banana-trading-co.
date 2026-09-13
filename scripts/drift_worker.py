import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.models import Card, Trade, PriceHistory
from app.redis_client import redis_client
from engine.pricing import LiquidityPool
from engine.drift import ActivityStats, apply_drift_tick

DRIFT_INTERVAL_SECONDS = 30
ACTIVITY_WINDOW_MINUTES = 5


async def compute_activity_stats(session, card_id: str) -> ActivityStats:
    window_start = datetime.now(timezone.utc) - timedelta(minutes=ACTIVITY_WINDOW_MINUTES)
    result = await session.scalars(
        select(Trade).where(Trade.card_id == card_id, Trade.created_at >= window_start)
    )
    trades = result.all()

    if not trades:
        return ActivityStats(recent_trade_count=0, net_demand=0.0)

    buys = sum(1 for t in trades if t.side == "buy")
    sells = sum(1 for t in trades if t.side == "sell")
    net_demand = (buys - sells) / len(trades)

    return ActivityStats(recent_trade_count=len(trades), net_demand=net_demand)


async def drift_one_card(card_id: str):
    """Applies one drift tick to a single card. Returns the new price,
    or None if the card no longer exists."""
    async with async_session_factory() as session:
        card = await session.scalar(
            select(Card).where(Card.id == card_id).with_for_update()
        )
        if card is None:
            return None

        stats = await compute_activity_stats(session, card_id)

        pool = LiquidityPool(
            currency_reserve=card.currency_reserve,
            card_reserve=card.card_reserve,
            fee_rate=card.fee_rate,
        )
        apply_drift_tick(pool, stats)

        card.currency_reserve = pool.currency_reserve
        card.card_reserve = pool.card_reserve
        session.add(PriceHistory(card_id=card_id, price=pool.price, event="drift"))
        await session.commit()

    await redis_client.publish(
        f"card:{card_id}:price",
        json.dumps({"card_id": card_id, "price": pool.price, "event": "drift"}),
    )
    return pool.price


async def tick_all_cards():
    async with async_session_factory() as session:
        card_ids = (await session.scalars(select(Card.id))).all()

    for card_id in card_ids:
        try:
            await drift_one_card(card_id)
        except Exception as e:
            print(f"Drift tick failed for card {card_id}: {e}")


async def main():
    print(f"Drift worker started. Ticking every {DRIFT_INTERVAL_SECONDS}s.")
    while True:
        await tick_all_cards()
        await asyncio.sleep(DRIFT_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())