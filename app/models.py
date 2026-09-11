import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    currency_balance: Mapped[float] = mapped_column(Float, default=1000.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    creator_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))

    total_supply: Mapped[float] = mapped_column(Float)
    currency_reserve: Mapped[float] = mapped_column(Float)
    card_reserve: Mapped[float] = mapped_column(Float)

    fee_rate: Mapped[float] = mapped_column(Float, default=0.01)
    cap_pct: Mapped[float] = mapped_column(Float, default=0.20)
    creator_stake_pct: Mapped[float] = mapped_column(Float, default=0.0)
    supply_model: Mapped[str] = mapped_column(String, default="fixed")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    card_id: Mapped[str] = mapped_column(String, ForeignKey("cards.id"), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    avg_cost_basis: Mapped[float] = mapped_column(Float, default=0.0)


class Trade(Base):
    """
    Immutable ledger. A row is inserted for every trade and never
    updated or deleted, this is the source of truth for what actually
    happened, independent of any derived state like balances.
    """
    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    card_id: Mapped[str] = mapped_column(String, ForeignKey("cards.id"), index=True)
    side: Mapped[str] = mapped_column(String)  # "buy" or "sell"
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    fee_amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )