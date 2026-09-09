from pydantic import BaseModel, Field, ConfigDict


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    currency_balance: float

class CardCreate(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    creator_id: str
    total_supply: float = Field(gt=0)
    initial_currency_reserve: float = Field(gt=0)
    initial_card_reserve: float = Field(gt=0)


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    creator_id: str
    total_supply: float
    currency_reserve: float
    card_reserve: float
    fee_rate: float
    cap_pct: float
    price: float

class TradeCreate(BaseModel):
    user_id: str
    card_id: str
    side: str = Field(pattern="^(buy|sell)$")
    amount: float = Field(gt=0)  # currency to spend (buy) or units to sell (sell)


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    card_id: str
    side: str
    quantity: float
    price: float
    fee_amount: float

class PortfolioItem(BaseModel):
    card_id: str
    card_name: str
    quantity: float
    avg_cost_basis: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class PortfolioOut(BaseModel):
    user_id: str
    currency_balance: float
    holdings: list[PortfolioItem]
    total_portfolio_value: float