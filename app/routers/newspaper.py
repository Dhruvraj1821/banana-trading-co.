from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import Card, User, Trade, PriceHistory
from app.schemas import Newspaper, GainerLoser, NewListing, WhaleTrade

router = APIRouter(prefix="/newspaper", tags=["newspaper"])

WINDOW_HOURS = 24
TOP_N = 3


@router.get("/latest", response_model=Newspaper)
async def get_latest_newspaper(db: AsyncSession = Depends(get_db_session)):
    window_start = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)

    cards = {c.id: c for c in (await db.scalars(select(Card))).all()}
    users = {u.id: u for u in (await db.scalars(select(User))).all()}

    # --- gainers / losers, from PriceHistory within the window ---
    history_rows = (
        await db.scalars(
            select(PriceHistory)
            .where(PriceHistory.created_at >= window_start)
            .order_by(PriceHistory.created_at.asc())
        )
    ).all()

    rows_by_card: dict[str, list] = {}
    for row in history_rows:
        rows_by_card.setdefault(row.card_id, []).append(row)

    movers = []
    for card_id, rows in rows_by_card.items():
        card = cards.get(card_id)
        if card is None or not rows:
            continue
        earliest_price = rows[0].price
        latest_price = rows[-1].price
        if earliest_price <= 0:
            continue
        pct_change = (latest_price - earliest_price) / earliest_price * 100
        movers.append(
            GainerLoser(
                card_id=card_id,
                card_name=card.name,
                pct_change=pct_change,
                latest_price=latest_price,
            )
        )

    movers_sorted = sorted(movers, key=lambda m: m.pct_change, reverse=True)
    top_gainers = movers_sorted[:TOP_N]

    gainer_ids = {g.card_id for g in top_gainers}
    loser_candidates = [m for m in movers_sorted if m.card_id not in gainer_ids]
    top_losers = list(reversed(loser_candidates[-TOP_N:])) if loser_candidates else []

    # --- new listings ---
    new_listings = [
        NewListing(
            card_id=card.id,
            card_name=card.name,
            creator_username=users[card.creator_id].username
            if card.creator_id in users
            else "unknown",
            total_supply=card.total_supply,
        )
        for card in cards.values()
        if card.created_at >= window_start
    ]

    # --- whale trades ---
    trades = (
        await db.scalars(select(Trade).where(Trade.created_at >= window_start))
    ).all()

    whale_candidates = []
    for trade in trades:
        card = cards.get(trade.card_id)
        user = users.get(trade.user_id)
        if card is None or user is None:
            continue
        whale_candidates.append(
            WhaleTrade(
                card_name=card.name,
                username=user.username,
                side=trade.side,
                currency_value=trade.quantity * trade.price,
            )
        )
    whale_candidates.sort(key=lambda t: t.currency_value, reverse=True)
    whale_trades = whale_candidates[:TOP_N]

    # --- headlines, template-filled from the real data above ---
    headlines = []
    for gainer in top_gainers:
        if gainer.pct_change > 0:
            headlines.append(f"{gainer.card_name} surges {gainer.pct_change:.1f}% amid heavy trading")
    for loser in top_losers:
        if loser.pct_change < 0:
            headlines.append(f"{loser.card_name} plunges {abs(loser.pct_change):.1f}% as investors flee")
    for listing in new_listings:
        headlines.append(f"{listing.card_name} debuts on the exchange, courtesy of {listing.creator_username}")
    for whale in whale_trades:
        verb = "scoops up" if whale.side == "buy" else "dumps"
        headlines.append(f"Mystery trader {verb} ${whale.currency_value:,.0f} of {whale.card_name}")

    if not headlines:
        headlines.append("Markets quiet. Nothing to report today.")

    return Newspaper(
        generated_at=datetime.now(timezone.utc).isoformat(),
        headlines=headlines,
        top_gainers=top_gainers,
        top_losers=top_losers,
        new_listings=new_listings,
        whale_trades=whale_trades,
    )