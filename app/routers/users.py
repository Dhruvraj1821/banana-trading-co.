from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import User, Card, Holding
from app.schemas import UserCreate, UserOut, PortfolioItem, PortfolioOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate, db: AsyncSession = Depends(get_db_session)
):
    existing = await db.scalar(
        select(User).where(User.username == payload.username)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(username=payload.username)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db_session)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/{user_id}/portfolio", response_model=PortfolioOut)
async def get_portfolio(user_id: str, db: AsyncSession = Depends(get_db_session)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.scalars(
        select(Holding).where(Holding.user_id == user_id, Holding.quantity > 0)
    )
    holdings = result.all()

    items = []
    for holding in holdings:
        card = await db.get(Card, holding.card_id)
        current_price = card.currency_reserve / card.card_reserve
        market_value = holding.quantity * current_price
        cost_total = holding.quantity * holding.avg_cost_basis
        unrealized_pnl = market_value - cost_total
        unrealized_pnl_pct = (
            (unrealized_pnl / cost_total * 100) if cost_total > 0 else 0.0
        )

        items.append(
            PortfolioItem(
                card_id=card.id,
                card_name=card.name,
                quantity=holding.quantity,
                avg_cost_basis=holding.avg_cost_basis,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
            )
        )

    total_value = user.currency_balance + sum(item.market_value for item in items)

    return PortfolioOut(
        user_id=user.id,
        currency_balance=user.currency_balance,
        holdings=items,
        total_portfolio_value=total_value,
    )