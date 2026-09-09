from engine.pricing import LiquidityPool
from engine.ownership import OwnershipLedger, OwnershipCapExceededError
from engine.pricing import InsufficientLiquidityError


def whale_single_big_buy(
    pool: LiquidityPool,
    ledger: OwnershipLedger,
    whale_id: str = "whale",
    attack_amount: float = 5000,
) -> dict:
    """
    Attempts to buy a huge amount in a single trade. A healthy engine
    should either reject this outright (cap exceeded) or let it through
    at a badly degraded average price (slippage), never at the pool's
    starting price.
    """
    starting_price = pool.price
    try:
        result = pool.buy(currency_in=attack_amount)
        ledger.record_buy(whale_id, result.net_amount)
        avg_price_paid = attack_amount / result.net_amount
        return {
            "blocked": False,
            "units_acquired": result.net_amount,
            "avg_price_paid": avg_price_paid,
            "starting_price": starting_price,
            "slippage_pct": (avg_price_paid / starting_price - 1) * 100,
        }
    except (OwnershipCapExceededError, InsufficientLiquidityError) as e:
        return {"blocked": True, "reason": str(e)}


def whale_split_buy_evasion(
    pool: LiquidityPool,
    ledger: OwnershipLedger,
    whale_id: str = "whale",
    total_amount: float = 5000,
    num_splits: int = 50,
) -> dict:
    """
    Attempts to dodge the ownership cap by breaking one big buy into
    many small chunks. Since the cap checks total holdings, not
    per-trade size, this should get blocked at whatever point the
    cumulative holding would cross the cap, same total limit as a
    single trade would face.
    """
    chunk = total_amount / num_splits
    total_units = 0.0
    successful_splits = 0

    for i in range(num_splits):
        try:
            result = pool.buy(currency_in=chunk)
            ledger.record_buy(whale_id, result.net_amount)
            total_units += result.net_amount
            successful_splits += 1
        except (OwnershipCapExceededError, InsufficientLiquidityError):
            break

    return {
        "total_units_acquired": total_units,
        "successful_splits": successful_splits,
        "attempted_splits": num_splits,
        "final_holding_pct_of_cap": total_units / ledger.max_allowed_holding()
        if ledger.max_allowed_holding() > 0
        else 0,
    }


def wash_trading_loop(
    pool: LiquidityPool,
    ledger: OwnershipLedger,
    trader_id: str = "washer",
    num_cycles: int = 20,
    amount_per_cycle: float = 50,
) -> dict:
    """
    Repeatedly buys then immediately sells the same position, checking
    whether fees successfully prevent any profit from leaking through
    pure buy/sell cycling.
    """
    net_currency_change = 0.0

    for _ in range(num_cycles):
        buy_result = pool.buy(currency_in=amount_per_cycle)
        ledger.record_buy(trader_id, buy_result.net_amount)

        sell_result = pool.sell(card_in=buy_result.net_amount)
        ledger.record_sell(trader_id, buy_result.net_amount)

        net_currency_change += sell_result.net_amount - amount_per_cycle

    return {
        "num_cycles": num_cycles,
        "net_currency_change": net_currency_change,
        "is_a_loss": net_currency_change < 0,
    }