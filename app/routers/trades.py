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
    current_avg_cost_basis = holding.avg_cost_basis if holding is not None else 0.0

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

        new_quantity = ledger.balance_of(payload.user_id)
        prior_cost_total = current_quantity * current_avg_cost_basis
        new_avg_cost_basis = (prior_cost_total + payload.amount) / new_quantity

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

        new_quantity = ledger.balance_of(payload.user_id)
        new_avg_cost_basis = current_avg_cost_basis if new_quantity > 0 else 0.0

    card.currency_reserve = pool.currency_reserve
    card.card_reserve = pool.card_reserve

    if holding is None:
        holding = Holding(
            user_id=payload.user_id,
            card_id=payload.card_id,
            quantity=new_quantity,
            avg_cost_basis=new_avg_cost_basis,
        )
        db.add(holding)
    else:
        holding.quantity = new_quantity
        holding.avg_cost_basis = new_avg_cost_basis

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