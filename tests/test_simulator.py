import random
import pytest
from engine.pricing import LiquidityPool
from engine.ownership import OwnershipLedger
from engine.simulator import simulate_normal_trading, price_series


def test_simulation_produces_history():
    pool = LiquidityPool(currency_reserve=10000, card_reserve=1000)
    ledger = OwnershipLedger(total_supply=1000, cap_pct=0.20)
    history = simulate_normal_trading(
        pool, ledger, num_ticks=50, num_traders=10, rng=random.Random(1)
    )
    assert len(history) > 0


def test_simulation_is_deterministic_with_same_seed():
    pool_a = LiquidityPool(currency_reserve=10000, card_reserve=1000)
    ledger_a = OwnershipLedger(total_supply=1000, cap_pct=0.20)
    history_a = simulate_normal_trading(
        pool_a, ledger_a, num_ticks=50, num_traders=10, rng=random.Random(99)
    )

    pool_b = LiquidityPool(currency_reserve=10000, card_reserve=1000)
    ledger_b = OwnershipLedger(total_supply=1000, cap_pct=0.20)
    history_b = simulate_normal_trading(
        pool_b, ledger_b, num_ticks=50, num_traders=10, rng=random.Random(99)
    )

    assert price_series(history_a) == price_series(history_b)


def test_no_player_ever_exceeds_ownership_cap():
    pool = LiquidityPool(currency_reserve=10000, card_reserve=1000)
    ledger = OwnershipLedger(total_supply=1000, cap_pct=0.20)
    simulate_normal_trading(
        pool, ledger, num_ticks=300, num_traders=20, rng=random.Random(5)
    )

    for trader_id, balance in ledger.holdings.items():
        assert balance <= ledger.max_allowed_holding() + 1e-6


def test_price_never_goes_negative_or_zero():
    pool = LiquidityPool(currency_reserve=10000, card_reserve=1000)
    ledger = OwnershipLedger(total_supply=1000, cap_pct=0.20)
    history = simulate_normal_trading(
        pool, ledger, num_ticks=300, num_traders=20, rng=random.Random(3)
    )
    assert all(record.price > 0 for record in history)


def test_more_traders_produces_more_trade_events():
    pool_small = LiquidityPool(currency_reserve=10000, card_reserve=1000)
    ledger_small = OwnershipLedger(total_supply=1000, cap_pct=0.20)
    history_small = simulate_normal_trading(
        pool_small, ledger_small, num_ticks=100, num_traders=5, rng=random.Random(1)
    )

    pool_big = LiquidityPool(currency_reserve=10000, card_reserve=1000)
    ledger_big = OwnershipLedger(total_supply=1000, cap_pct=0.20)
    history_big = simulate_normal_trading(
        pool_big, ledger_big, num_ticks=100, num_traders=50, rng=random.Random(1)
    )

    small_trades = sum(1 for r in history_small if r.event == "trade")
    big_trades = sum(1 for r in history_big if r.event == "trade")
    assert big_trades > small_trades