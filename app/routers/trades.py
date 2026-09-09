from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import Card, User, Holding, Trade
from app.schemas import TradeCreate, TradeOut
from engine.pricing import LiquidityPool, InsufficientLiquidityError
from engine.ownership import OwnershipLedger, OwnershipCapExceededError

router = APIRouter(prefix="/trades", tags=["trades"])


@router.post("/", response_model=TradeOut, status_code=201)
async def execute_trade(
    payload: TradeCreate, db: AsyncSession = Depends(get_db_session)
):
    # Lock order: card, then user, then holding. Always this order,
    # on every code path, to prevent deadlocks between concurrent trades.
    card = await db.scalar(
        select(Card).where(Card.id == payload.card_id).with_for_update()
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")

    user = await db.scalar(
        select(User).where(User.id == payload.user_id).with_for_update()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    holding = await db.scalar(
        select(Holding)
        .where(Holding.user_id == payload.user_id, Holding.card_id == payload.card_id)
        .with_for_update()
    )
    current_quantity = holding.quantity if holding is not None else 0.0

    pool = LiquidityPool(
        currency_reserve=card.currency_reserve,
        card_reserve=card.card_reserve,
        fee_rate=card.fee_rate,
    )
    ledger = OwnershipLedger(total_supply=card.total_supply, cap_pct=card.cap_pct)
    ledger.holdings[payload.user_id] = current_quantity

    if payload.side == "buy":
        if user.currency_balance < payload.amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        try:
            result = pool.buy(currency_in=payload.amount)
            ledger.record_buy(payload.user_id, result.net_amount)
        except (InsufficientLiquidityError, OwnershipCapExceededError) as e:
            raise HTTPException(status_code=400, detail=str(e))

        user.currency_balance -= payload.amount
        trade_quantity = result.net_amount
        trade_price = payload.amount / result.net_amount

    else:  # sell
        if current_quantity < payload.amount:
            raise HTTPException(status_code=400, detail="Insufficient holdings")
        try:
            result = pool.sell(card_in=payload.amount)
            ledger.record_sell(payload.user_id, payload.amount)
        except InsufficientLiquidityError as e:
            raise HTTPException(status_code=400, detail=str(e))

        user.currency_balance += result.net_amount
        trade_quantity = payload.amount
        trade_price = result.net_amount / payload.amount

    # Persist the pool's updated reserves back onto the card row
    card.currency_reserve = pool.currency_reserve
    card.card_reserve = pool.card_reserve

    new_quantity = ledger.balance_of(payload.user_id)
    if holding is None:
        holding = Holding(
            user_id=payload.user_id, card_id=payload.card_id, quantity=new_quantity
        )
        db.add(holding)
    else:
        holding.quantity = new_quantity

    trade = Trade(
        user_id=payload.user_id,
        card_id=payload.card_id,
        side=payload.side,
        quantity=trade_quantity,
        price=trade_price,
        fee_amount=result.fee_amount,
    )
    db.add(trade)

    await db.commit()
    await db.refresh(trade)
    return trade