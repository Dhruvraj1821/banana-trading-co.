import random
import matplotlib.pyplot as plt

from engine.pricing import LiquidityPool
from engine.ownership import OwnershipLedger
from engine.simulator import simulate_normal_trading, price_series
from engine.attacks import whale_single_big_buy, whale_split_buy_evasion, wash_trading_loop


def run_normal_trading_and_plot():
    pool = LiquidityPool(
        currency_reserve=100_000, card_reserve=10_000, fee_rate=0.01
    )
    ledger = OwnershipLedger(total_supply=10_000, cap_pct=0.20)

    history = simulate_normal_trading(
        pool, ledger, num_ticks=1000, num_traders=30, rng=random.Random(42)
    )
    prices = price_series(history)

    plt.figure(figsize=(10, 5))
    plt.plot(prices)
    plt.title("Card Price Over 1000 Ticks (30 traders)")
    plt.xlabel("Event index")
    plt.ylabel("Price")
    plt.savefig("results_normal_trading.png")
    print(f"Saved chart to results_normal_trading.png")
    print(f"Starting price: {prices[0]:.4f}, Ending price: {prices[-1]:.4f}")
    print(f"Min price: {min(prices):.4f}, Max price: {max(prices):.4f}")


def run_whale_attacks():
    print("\n--- Whale Attack: Single Big Buy ---")
    pool = LiquidityPool(currency_reserve=100_000, card_reserve=10_000, fee_rate=0.01)
    ledger = OwnershipLedger(total_supply=10_000, cap_pct=0.20)
    result = whale_single_big_buy(pool, ledger, attack_amount=50_000)
    print(result)

    print("\n--- Whale Attack: Split-Buy Cap Evasion ---")
    pool = LiquidityPool(currency_reserve=100_000, card_reserve=10_000, fee_rate=0.01)
    ledger = OwnershipLedger(total_supply=10_000, cap_pct=0.20)
    result = whale_split_buy_evasion(pool, ledger, total_amount=50_000, num_splits=100)
    print(result)

    print("\n--- Wash Trading Loop ---")
    pool = LiquidityPool(currency_reserve=100_000, card_reserve=10_000, fee_rate=0.01)
    ledger = OwnershipLedger(total_supply=10_000, cap_pct=0.20)
    result = wash_trading_loop(pool, ledger, num_cycles=50, amount_per_cycle=200)
    print(result)

    print("\n--- Whale Attack: Single Big Buy (cap disabled, slippage only) ---")
    pool = LiquidityPool(currency_reserve=100_000, card_reserve=10_000, fee_rate=0.01)
    ledger = OwnershipLedger(total_supply=10_000, cap_pct=1.0)
    result = whale_single_big_buy(pool, ledger, attack_amount=50_000)
    print(result)


if __name__ == "__main__":
    run_normal_trading_and_plot()
    run_whale_attacks()