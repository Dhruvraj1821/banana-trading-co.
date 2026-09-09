from dataclasses import dataclass, field


class OwnershipCapExceededError(Exception):
    """Raised when a buy would push a player's holding above the cap."""
    pass


@dataclass
class OwnershipLedger:
    """
    Tracks how many units of one card each player holds, and enforces
    a max percentage of circulating supply any single player can own.
    """
    circulating_supply: float
    cap_pct: float = 0.20  # no player may hold more than 20% by default
    holdings: dict = field(default_factory=dict)

    def balance_of(self, player_id: str) -> float:
        return self.holdings.get(player_id, 0)

    def max_allowed_holding(self) -> float:
        return self.circulating_supply * self.cap_pct

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

    def grow_supply(self, new_units: float) -> None:
        """
        Call this whenever the pool's card_reserve changes due to a buy
        pulling units out of circulation into a player's hands, or a
        sell returning them. Circulating supply here means units that
        exist and could theoretically be owned, not units sitting in
        the pool.
        """
        self.circulating_supply += new_units