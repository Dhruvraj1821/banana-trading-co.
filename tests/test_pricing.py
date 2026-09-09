import pytest
from engine.pricing import LiquidityPool, InsufficientLiquidityError, FeeSplit, TradeResult


def test_initial_price():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    assert pool.price == 10


def test_buy_increases_price():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    starting_price = pool.price
    pool.buy(currency_in=100)
    assert pool.price > starting_price


def test_sell_decreases_price():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    starting_price = pool.price
    pool.sell(card_in=10)
    assert pool.price < starting_price


def test_k_stays_constant_across_buy():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    k_before = pool.k
    pool.buy(currency_in=100)
    assert pool.k == pytest.approx(k_before)


def test_larger_buy_has_worse_average_price():
    """This is the slippage property: buying more per trade should cost
    a higher average price per unit than buying less."""
    small_pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    small_result = small_pool.buy(currency_in=50)
    small_avg_price = 50 / small_result.net_amount

    big_pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    big_result = big_pool.buy(currency_in=500)
    big_avg_price = 500 / big_result.net_amount

    assert big_avg_price > small_avg_price


def test_buy_then_sell_same_amount_nets_a_loss():
    """Without fees, this should be roughly break-even but never a
    profit, proving the curve alone doesn't allow free money."""
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    buy_result = pool.buy(currency_in=100)
    sell_result = pool.sell(card_in=buy_result.net_amount)
    assert sell_result.net_amount <= 100


def test_buy_rejects_non_positive_input():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    with pytest.raises(ValueError):
        pool.buy(currency_in=0)


def test_sell_rejects_selling_more_than_reserve():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    with pytest.raises(InsufficientLiquidityError):
        pool.sell(card_in=100)


def test_buy_fee_is_taken():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100, fee_rate=0.01)
    result = pool.buy(currency_in=100)
    assert result.fee_amount == pytest.approx(1.0)  # 1% of 100


def test_fee_split_adds_up_to_total_fee():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100, fee_rate=0.01)
    result = pool.buy(currency_in=100)
    total_split = result.creator_fee + result.burn_fee + result.treasury_fee
    assert total_split == pytest.approx(result.fee_amount)


def test_wash_trading_is_a_guaranteed_loss():
    """Buying then immediately selling the same position should cost
    the fee twice, and never return a profit."""
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100, fee_rate=0.01)
    starting_currency_spent = 100
    buy_result = pool.buy(currency_in=starting_currency_spent)
    sell_result = pool.sell(card_in=buy_result.net_amount)
    assert sell_result.net_amount < starting_currency_spent


def test_invalid_fee_split_raises():
    with pytest.raises(ValueError):
        FeeSplit(creator_pct=0.5, burn_pct=0.5, treasury_pct=0.5)  # sums to 1.5