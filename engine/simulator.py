import random
from dataclasses import dataclass
from engine.pricing import LiquidityPool
from engine.ownership import OwnershipLedger
from engine.drift import ActivityStats, apply_drift_tick


@dataclass
class SimulationRecord:
    tick: int
    price: float
    event: str  # "trade" or "drift"


def simulate_normal_trading(
    pool: LiquidityPool,
    ledger: OwnershipLedger,
    num_ticks: int = 500,
    num_traders: int = 20,
    trade_probability: float = 0.3,
    rng: random.Random = None,
) -> list:
    """
    Simulates num_ticks time steps. On each tick, every trader has a
    chance to place a random buy or sell (sized relative to their own
    holdings for sells), then one idle drift tick fires for the card,
    scaled by how much real trading happened that tick.

    Returns a list of SimulationRecord entries tracking price over time.
    Failed trades (cap exceeded, insufficient liquidity) are silently
    skipped, since a real player's failed trade just doesn't happen.
    """
    if rng is None:
        rng = random.Random()

    trader_ids = [f"trader_{i}" for i in range(num_traders)]
    history = []

    for tick in range(num_ticks):
        trade_count = 0
        net_demand_accumulator = 0.0

        for trader_id in trader_ids:
            if rng.random() >= trade_probability:
                continue

            side = rng.choice(["buy", "sell"])
            try:
                if side == "buy":
                    amount = rng.uniform(1, 50)
                    result = pool.buy(currency_in=amount)
                    ledger.record_buy(trader_id, result.net_amount)
                    net_demand_accumulator += 1
                else:
                    balance = ledger.balance_of(trader_id)
                    if balance <= 0:
                        continue
                    amount = rng.uniform(0.01, balance)
                    pool.sell(card_in=amount)
                    ledger.record_sell(trader_id, amount)
                    net_demand_accumulator -= 1

                trade_count += 1
                history.append(SimulationRecord(tick, pool.price, "trade"))
            except Exception:
                # A failed trade (cap hit, liquidity too thin) just
                # doesn't happen, same as a rejected click in the UI.
                pass

        stats = ActivityStats(
            recent_trade_count=trade_count,
            net_demand=max(-1.0, min(1.0, net_demand_accumulator / max(1, num_traders))),
        )
        apply_drift_tick(pool, stats, rng=rng)
        history.append(SimulationRecord(tick, pool.price, "drift"))

    return history


def price_series(history: list) -> list:
    """Convenience helper: just the price values, in order."""
    return [record.price for record in history]