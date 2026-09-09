from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import Card, User
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

    card = Card(
        name=payload.name,
        creator_id=payload.creator_id,
        total_supply=payload.total_supply,
        currency_reserve=payload.initial_currency_reserve,
        card_reserve=payload.initial_card_reserve,
    )
    db.add(card)
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