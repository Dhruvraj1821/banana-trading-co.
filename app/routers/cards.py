from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import Card, User, Holding
from app.schemas import CardCreate, CardOut

router = APIRouter(prefix="/cards", tags=["cards"])

def to_card_out(card: Card) -> CardOut:
    return CardOut(
        id=card.id,
        name=card.name,
        creator_id=card.creator_id,
        total_supply=card.total_supply,
        currency_reserve=card.currency_reserve,
        card_reserve=card.card_reserve,
        fee_rate=card.fee_rate,
        cap_pct=card.cap_pct,
        creator_stake_pct=card.creator_stake_pct,
        supply_model=card.supply_model,
        price=card.currency_reserve / card.card_reserve,
    )


@router.post("/", response_model=CardOut, status_code=201)
async def create_card(
    payload: CardCreate, db: AsyncSession = Depends(get_db_session)
):
    creator = await db.get(User, payload.creator_id)
    if creator is None:
        raise HTTPException(status_code=404, detail="Creator not found")

    existing = await db.scalar(select(Card).where(Card.name == payload.name))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Card name already taken")

    if payload.supply_model == "unlimited":
        raise HTTPException(
            status_code=400, detail="Unlimited supply model is not implemented yet"
        )

    default_cap_pct = 0.20
    if payload.creator_stake_pct > default_cap_pct:
        raise HTTPException(
            status_code=400,
            detail=(
                f"creator_stake_pct ({payload.creator_stake_pct}) cannot exceed "
                f"the ownership cap ({default_cap_pct}); a card cannot launch "
                f"already violating its own anti-whale rule"
            ),
        )

    stake_units = payload.total_supply * payload.creator_stake_pct
    if stake_units > payload.initial_card_reserve:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Creator stake requires {stake_units:.2f} units, but "
                f"initial_card_reserve only provides {payload.initial_card_reserve:.2f}. "
                f"Increase initial_card_reserve or lower creator_stake_pct."
            ),
        )

    card = Card(
        name=payload.name,
        creator_id=payload.creator_id,
        total_supply=payload.total_supply,
        currency_reserve=payload.initial_currency_reserve,
        card_reserve=payload.initial_card_reserve - stake_units,
        creator_stake_pct=payload.creator_stake_pct,
        supply_model=payload.supply_model,
    )
    db.add(card)
    await db.flush()  # assigns card.id without ending the transaction

    if stake_units > 0:
        stake_holding = Holding(
            user_id=payload.creator_id,
            card_id=card.id,
            quantity=stake_units,
            avg_cost_basis=0.0,
        )
        db.add(stake_holding)

    await db.commit()
    await db.refresh(card)
    return to_card_out(card)

@router.get("/", response_model=list[CardOut])
async def list_cards(db: AsyncSession = Depends(get_db_session)):
    result = await db.scalars(select(Card).order_by(Card.created_at.desc()))
    return [to_card_out(card) for card in result.all()]


@router.get("/{card_id}", response_model=CardOut)
async def get_card(card_id: str, db: AsyncSession = Depends(get_db_session)):
    card = await db.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return to_card_out(card)