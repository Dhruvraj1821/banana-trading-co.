import pytest
from engine.ownership import OwnershipLedger, OwnershipCapExceededError


def test_new_player_has_zero_balance():
    ledger = OwnershipLedger(circulating_supply=1000)
    assert ledger.balance_of("alice") == 0


def test_record_buy_increases_balance():
    ledger = OwnershipLedger(circulating_supply=1000, cap_pct=0.20)
    ledger.record_buy("alice", 50)
    assert ledger.balance_of("alice") == 50


def test_buy_within_cap_succeeds():
    ledger = OwnershipLedger(circulating_supply=1000, cap_pct=0.20)
    # cap is 20% of 1000 = 200 units
    ledger.record_buy("alice", 199)
    assert ledger.balance_of("alice") == 199


def test_buy_exceeding_cap_raises():
    ledger = OwnershipLedger(circulating_supply=1000, cap_pct=0.20)
    # cap is 200 units
    with pytest.raises(OwnershipCapExceededError):
        ledger.record_buy("alice", 201)


def test_buy_exceeding_cap_across_multiple_trades_raises():
    """The cap should apply to total holdings, not just one trade at
    a time. This is what stops a whale from getting around the cap by
    splitting one big buy into many small ones."""
    ledger = OwnershipLedger(circulating_supply=1000, cap_pct=0.20)
    ledger.record_buy("alice", 100)
    ledger.record_buy("alice", 99)
    with pytest.raises(OwnershipCapExceededError):
        ledger.record_buy("alice", 5)  # would push to 204, over the 200 cap


def test_failed_buy_does_not_change_balance():
    ledger = OwnershipLedger(circulating_supply=1000, cap_pct=0.20)
    with pytest.raises(OwnershipCapExceededError):
        ledger.record_buy("alice", 500)
    assert ledger.balance_of("alice") == 0


def test_cap_is_per_player_not_shared():
    ledger = OwnershipLedger(circulating_supply=1000, cap_pct=0.20)
    ledger.record_buy("alice", 199)
    ledger.record_buy("bob", 199)
    assert ledger.balance_of("alice") == 199
    assert ledger.balance_of("bob") == 199


def test_record_sell_decreases_balance():
    ledger = OwnershipLedger(circulating_supply=1000, cap_pct=0.20)
    ledger.record_buy("alice", 100)
    ledger.record_sell("alice", 40)
    assert ledger.balance_of("alice") == 60


def test_sell_more_than_held_raises():
    ledger = OwnershipLedger(circulating_supply=1000, cap_pct=0.20)
    ledger.record_buy("alice", 50)
    with pytest.raises(ValueError):
        ledger.record_sell("alice", 100)


def test_selling_then_rebuying_up_to_cap_succeeds():
    """Proves the cap tracks current balance, not lifetime purchases,
    so selling frees up room to buy again."""
    ledger = OwnershipLedger(circulating_supply=1000, cap_pct=0.20)
    ledger.record_buy("alice", 199)
    ledger.record_sell("alice", 100)
    ledger.record_buy("alice", 99)  # back up to 198, still under 200
    assert ledger.balance_of("alice") == 198