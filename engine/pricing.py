from dataclasses import dataclass


class InsufficientLiquidityError(Exception):
    """Raised when a trade would drain a reserve to zero or below."""
    pass


@dataclass
class FeeSplit:
    """How a trade's fee is distributed."""
    creator_pct: float = 0.30
    burn_pct: float = 0.40
    treasury_pct: float = 0.30

    def __post_init__(self):
        total = self.creator_pct + self.burn_pct + self.treasury_pct
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Fee split must sum to 1.0, got {total}")


@dataclass
class TradeResult:
    """What a buy or sell actually did, broken down for the caller."""
    gross_amount: float      # what the trader paid in (buy) or would get before fee (sell)
    fee_amount: float        # total fee taken
    net_amount: float        # what actually moved the reserves / what trader received
    creator_fee: float
    burn_fee: float
    treasury_fee: float


@dataclass
class LiquidityPool:
    currency_reserve: float
    card_reserve: float
    fee_rate: float = 0.01              # 1% default trading fee
    fee_split: FeeSplit = None

    def __post_init__(self):
        if self.fee_split is None:
            self.fee_split = FeeSplit()

    @property
    def price(self) -> float:
        return self.currency_reserve / self.card_reserve

    @property
    def k(self) -> float:
        return self.currency_reserve * self.card_reserve

    def _split_fee(self, fee_amount: float) -> tuple:
        creator_fee = fee_amount * self.fee_split.creator_pct
        burn_fee = fee_amount * self.fee_split.burn_pct
        treasury_fee = fee_amount * self.fee_split.treasury_pct
        return creator_fee, burn_fee, treasury_fee

    def buy(self, currency_in: float) -> TradeResult:
        """
        Spend `currency_in` currency to buy card units.
        The fee is taken off the top before it reaches the reserves.
        """
        if currency_in <= 0:
            raise ValueError("currency_in must be positive")

        fee_amount = currency_in * self.fee_rate
        currency_after_fee = currency_in - fee_amount

        k = self.k
        new_currency_reserve = self.currency_reserve + currency_after_fee
        new_card_reserve = k / new_currency_reserve
        card_out = self.card_reserve - new_card_reserve

        if new_card_reserve <= 0:
            raise InsufficientLiquidityError(
                "Trade would drain the card reserve to zero or below"
            )

        self.currency_reserve = new_currency_reserve
        self.card_reserve = new_card_reserve

        creator_fee, burn_fee, treasury_fee = self._split_fee(fee_amount)

        return TradeResult(
            gross_amount=card_out,
            fee_amount=fee_amount,
            net_amount=card_out,
            creator_fee=creator_fee,
            burn_fee=burn_fee,
            treasury_fee=treasury_fee,
        )

    def sell(self, card_in: float) -> TradeResult:
        """
        Sell `card_in` card units back into the pool.
        The fee is taken off the currency the trader would otherwise
        receive.
        """
        if card_in <= 0:
            raise ValueError("card_in must be positive")
        if card_in >= self.card_reserve:
            raise InsufficientLiquidityError(
                "Cannot sell more than the pool's card reserve"
            )

        k = self.k
        new_card_reserve = self.card_reserve + card_in
        new_currency_reserve = k / new_card_reserve
        currency_out_gross = self.currency_reserve - new_currency_reserve

        fee_amount = currency_out_gross * self.fee_rate
        currency_out_net = currency_out_gross - fee_amount

        self.currency_reserve = new_currency_reserve
        self.card_reserve = new_card_reserve

        creator_fee, burn_fee, treasury_fee = self._split_fee(fee_amount)

        return TradeResult(
            gross_amount=currency_out_gross,
            fee_amount=fee_amount,
            net_amount=currency_out_net,
            creator_fee=creator_fee,
            burn_fee=burn_fee,
            treasury_fee=treasury_fee,
        )