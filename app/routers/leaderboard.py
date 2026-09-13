from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import User, Card, Holding, Trade
from app.schemas import LeaderboardEntry, CreatorLeaderboardEntry
from app.constants import TREASURY_USERNAME, STARTING_BALANCE

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


async def _compute_net_worths(db: AsyncSession) -> list[LeaderboardEntry]:
    """
    Net worth = currency balance + market value of every holding, marked
    at each card's current price. Computed fresh per request rather than
    cached, a legitimate optimization for later at real scale, not
    necessary yet.
    """
    users = (
        await db.scalars(select(User).where(User.username != TREASURY_USERNAME))
    ).all()
    cards_by_id = {c.id: c for c in (await db.scalars(select(Card))).all()}

    entries = []
    for user in users:
        holdings = (
            await db.scalars(
                select(Holding).where(Holding.user_id == user.id, Holding.quantity > 0)
            )
        ).all()

        holdings_value = 0.0
        for holding in holdings:
            card = cards_by_id.get(holding.card_id)
            if card is None:
                continue
            price = card.currency_reserve / card.card_reserve
            holdings_value += holding.quantity * price

        net_worth = user.currency_balance + holdings_value
        roi_pct = (net_worth - STARTING_BALANCE) / STARTING_BALANCE * 100

        entries.append(
            LeaderboardEntry(
                user_id=user.id,
                username=user.username,
                net_worth=net_worth,
                roi_pct=roi_pct,
            )
        )
    return entries


@router.get("/networth", response_model=list[LeaderboardEntry])
async def leaderboard_networth(db: AsyncSession = Depends(get_db_session)):
    entries = await _compute_net_worths(db)
    entries.sort(key=lambda e: e.net_worth, reverse=True)
    return entries


@router.get("/roi", response_model=list[LeaderboardEntry])
async def leaderboard_roi(db: AsyncSession = Depends(get_db_session)):
    entries = await _compute_net_worths(db)
    entries.sort(key=lambda e: e.roi_pct, reverse=True)
    return entries


@router.get("/creators", response_model=list[CreatorLeaderboardEntry])
async def leaderboard_creators(db: AsyncSession = Depends(get_db_session)):
    users = (
        await db.scalars(select(User).where(User.username != TREASURY_USERNAME))
    ).all()
    cards = (await db.scalars(select(Card))).all()
    trades = (await db.scalars(select(Trade))).all()

    card_creator_by_card_id = {c.id: c.creator_id for c in cards}

    card_count_by_creator: dict[str, int] = {}
    for card in cards:
        card_count_by_creator[card.creator_id] = card_count_by_creator.get(card.creator_id, 0) + 1

    volume_by_creator: dict[str, float] = {}
    for trade in trades:
        creator_id = card_creator_by_card_id.get(trade.card_id)
        if creator_id is None:
            continue
        volume_by_creator[creator_id] = (
            volume_by_creator.get(creator_id, 0.0) + trade.quantity * trade.price
        )

    entries = [
        CreatorLeaderboardEntry(
            user_id=user.id,
            username=user.username,
            card_count=card_count_by_creator[user.id],
            total_trading_volume=volume_by_creator.get(user.id, 0.0),
        )
        for user in users
        if user.id in card_count_by_creator
    ]
    entries.sort(key=lambda e: e.total_trading_volume, reverse=True)
    return entries