import pytest
from engine.pricing import LiquidityPool, InsufficientLiquidityError


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
    small_out = small_pool.buy(currency_in=50)
    small_avg_price = 50 / small_out

    big_pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    big_out = big_pool.buy(currency_in=500)
    big_avg_price = 500 / big_out

    assert big_avg_price > small_avg_price


def test_buy_then_sell_same_amount_nets_a_loss():
    """Without fees yet, this should be roughly break-even but never a
    profit, proving the curve alone doesn't allow free money."""
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    cards_bought = pool.buy(currency_in=100)
    currency_back = pool.sell(card_in=cards_bought)
    assert currency_back <= 100


def test_buy_rejects_non_positive_input():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    with pytest.raises(ValueError):
        pool.buy(currency_in=0)


def test_sell_rejects_selling_more_than_reserve():
    pool = LiquidityPool(currency_reserve=1000, card_reserve=100)
    with pytest.raises(InsufficientLiquidityError):
        pool.sell(card_in=100)