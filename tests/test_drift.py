import random
import pytest
from engine.pricing import LiquidityPool
from engine.drift import ActivityStats, compute_drift_pct, apply_drift_tick


def test_drift_is_zero_activity_by_default():
    stats = ActivityStats()
    assert stats.recent_trade_count == 0
    assert stats.net_demand == 0.0


def test_drift_stays_within_clamp():
    rng = random.Random(1)
    stats = ActivityStats(recent_trade_count=0, net_demand=0.0)
    for _ in range(1000):
        drift = compute_drift_pct(stats, max_drift_pct=0.03, rng=rng)
        assert -0.03 <= drift <= 0.03


def test_quiet_card_has_higher_volatility_than_active_card():
    """Same seed, same starting conditions, only trade count differs.
    Quiet card's drift magnitude should tend to be larger."""
    quiet_stats = ActivityStats(recent_trade_count=0)
    active_stats = ActivityStats(recent_trade_count=50)

    quiet_drifts = [
        compute_drift_pct(quiet_stats, rng=random.Random(seed))
        for seed in range(200)
    ]
    active_drifts = [
        compute_drift_pct(active_stats, rng=random.Random(seed))
        for seed in range(200)
    ]

    avg_quiet_magnitude = sum(abs(d) for d in quiet_drifts) / len(quiet_drifts)
    avg_active_magnitude = sum(abs(d) for d in active_drifts) / len(active_drifts)

    assert avg_quiet_magnitude > avg_active_magnitude


def test_positive_net_demand_biases_drift_upward():
    """With a fixed seed, positive net demand should push drift higher
    than the same seed with zero net demand."""
    seed = 42
    neutral_stats = ActivityStats(recent_trade_count=10, net_demand=0.0)
    bullish_stats = ActivityStats(recent_trade_count=10, net_demand=1.0)

    neutral_drift = compute_drift_pct(neutral_stats, rng=random.Random(seed))
    bullish_drift = compute_drift_pct(bullish_stats, rng=random.Random(seed))

    assert bullish_drift > neutral_drift


def test_apply_drift_tick_changes_price():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    stats = ActivityStats(recent_trade_count=0, net_demand=0.0)
    starting_price = pool.price

    apply_drift_tick(pool, stats, rng=random.Random(7))

    assert pool.price != starting_price


def test_apply_drift_tick_returns_the_applied_drift():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    stats = ActivityStats()
    drift = apply_drift_tick(pool, stats, rng=random.Random(7))
    assert isinstance(drift, float)


def test_extreme_max_drift_still_respects_clamp():
    rng = random.Random(3)
    stats = ActivityStats(recent_trade_count=0, net_demand=0.0)
    drift = compute_drift_pct(
        stats, base_volatility=10.0, max_drift_pct=0.05, rng=rng
    )
    assert -0.05 <= drift <= 0.05