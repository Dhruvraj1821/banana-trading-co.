import random
from dataclasses import dataclass


@dataclass
class ActivityStats:
    """
    Rolling stats about recent trading on a card, used to scale and
    bias the drift tick. In Phase 2 this will be computed from real
    trade history; for now it's just passed in directly so drift logic
    can be tested in isolation.
    """
    recent_trade_count: int = 0        # trades in the current window
    net_demand: float = 0.0            # -1.0 (all selling) to 1.0 (all buying)


def compute_drift_pct(
    activity: ActivityStats,
    base_volatility: float = 0.02,
    momentum_weight: float = 0.01,
    max_drift_pct: float = 0.03,
    rng: random.Random = None,
) -> float:
    """
    Returns a signed percentage to apply to a pool's currency_reserve
    for one idle drift tick.

    Volatility scales down as trade activity goes up, so busy cards
    are driven mostly by real trades and quiet cards still move.
    """
    if rng is None:
        rng = random

    activity_dampener = 1.0 / (1.0 + activity.recent_trade_count)
    effective_volatility = base_volatility * activity_dampener

    random_component = rng.gauss(mu=0.0, sigma=effective_volatility)
    momentum_component = momentum_weight * activity.net_demand

    drift_pct = random_component + momentum_component

    return max(-max_drift_pct, min(max_drift_pct, drift_pct))


def apply_drift_tick(pool, activity: ActivityStats, **kwargs) -> float:
    """
    Applies one drift tick to a pool's currency_reserve in place.
    Returns the drift percentage that was applied.
    """
    drift_pct = compute_drift_pct(activity, **kwargs)
    pool.currency_reserve *= (1 + drift_pct)
    return drift_pct