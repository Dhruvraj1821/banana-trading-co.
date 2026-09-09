from dataclasses import dataclass, field


class OwnershipCapExceededError(Exception):
    """Raised when a buy would push a player's holding above the cap."""
    pass


@dataclass
class OwnershipLedger:
    """
    Tracks how many units of one card each player holds, and enforces
    a max percentage of the card's total supply any single player can
    own.

    total_supply is fixed at the card's launch (how many units could
    ever exist for a fixed-supply card), not how many units players
    currently hold. Using a growing "circulating supply" as the cap
    basis creates a bootstrapping deadlock: the very first buyer would
    always own 100% of whatever has been traded out so far, which
    breaks any cap below 100% before a single trade can happen.
    """
    total_supply: float
    cap_pct: float = 0.20
    holdings: dict = field(default_factory=dict)

    def balance_of(self, player_id: str) -> float:
        return self.holdings.get(player_id, 0)

    def max_allowed_holding(self) -> float:
        return self.total_supply * self.cap_pct

    def record_buy(self, player_id: str, units: float) -> None:
        """
        Adds `units` to the player's holding, after checking the cap.
        Raises OwnershipCapExceededError if the cap would be exceeded.
        Call this only after a successful LiquidityPool.buy().
        """
        current = self.balance_of(player_id)
        new_balance = current + units

        if new_balance > self.max_allowed_holding():
            raise OwnershipCapExceededError(
                f"Player would hold {new_balance:.2f} units, "
                f"cap is {self.max_allowed_holding():.2f}"
            )

        self.holdings[player_id] = new_balance

    def record_sell(self, player_id: str, units: float) -> None:
        """Removes `units` from the player's holding."""
        current = self.balance_of(player_id)
        if units > current:
            raise ValueError(
                f"Player only holds {current:.2f} units, cannot sell {units:.2f}"
            )
        self.holdings[player_id] = current - units