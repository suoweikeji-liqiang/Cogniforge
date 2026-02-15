from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.models.entities.user import User, ModelCard
from app.schemas.model_card import (
    ModelCardCreate,
    ModelCardUpdate,
    ModelCardResponse,
    CounterExampleInput,
    MigrationInput,
)
from app.api.routes.auth import get_current_user
from app.services.model_os_service import model_os_service

router = APIRouter(prefix="/model-cards", tags=["Model Cards"])


@router.post("/", response_model=ModelCardResponse, status_code=201)
async def create_model_card(
    card_data: ModelCardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    model_data = await model_os_service.create_model_card(
        user_id=str(current_user.id),
        title=card_data.title,
        description=card_data.user_notes or "",
        associated_concepts=card_data.examples,
    )
    
    db_card = ModelCard(
        user_id=current_user.id,
        title=card_data.title,
        concept_maps=model_data.get("concept_maps"),
        user_notes=card_data.user_notes,
        examples=card_data.examples or model_data.get("examples", []),
        counter_examples=model_data.get("limitations", []),
    )
    
    db.add(db_card)
    await db.commit()
    await db.refresh(db_card)
    
    return db_card


@router.get("/", response_model=List[ModelCardResponse])
async def list_model_cards(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ModelCard)
        .where(ModelCard.user_id == current_user.id)
        .order_by(ModelCard.created_at.desc())
    )
    cards = result.scalars().all()
    return cards


@router.get("/{card_id}", response_model=ModelCardResponse)
async def get_model_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ModelCard).where(
            ModelCard.id == card_id,
            ModelCard.user_id == current_user.id
        )
    )
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(status_code=404, detail="Model card not found")
    
    return card


@router.put("/{card_id}", response_model=ModelCardResponse)
async def update_model_card(
    card_id: UUID,
    card_data: ModelCardUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ModelCard).where(
            ModelCard.id == card_id,
            ModelCard.user_id == current_user.id
        )
    )
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(status_code=404, detail="Model card not found")
    
    if card_data.title:
        card.title = card_data.title
    if card_data.concept_maps:
        card.concept_maps = card_data.concept_maps
    if card_data.user_notes:
        card.user_notes = card_data.user_notes
    if card_data.examples:
        card.examples = card_data.examples
    if card_data.counter_examples:
        card.counter_examples = card_data.counter_examples
    if card_data.migration_attempts:
        card.migration_attempts = card_data.migration_attempts
    
    card.version += 1
    
    await db.commit()
    await db.refresh(card)
    
    return card


@router.delete("/{card_id}", status_code=204)
async def delete_model_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ModelCard).where(
            ModelCard.id == card_id,
            ModelCard.user_id == current_user.id
        )
    )
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(status_code=404, detail="Model card not found")
    
    await db.delete(card)
    await db.commit()
    
    return None


@router.post("/counter-examples")
async def generate_counter_examples(
    input_data: CounterExampleInput,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ModelCard).where(
            ModelCard.id == input_data.model_id,
            ModelCard.user_id == current_user.id
        )
    )
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(status_code=404, detail="Model card not found")
    
    counter_examples = await model_os_service.generate_counter_examples(
        model_title=card.title,
        model_concepts=card.examples,
        user_response=input_data.concept,
    )
    
    card.counter_examples = counter_examples
    card.version += 1
    
    await db.commit()
    await db.refresh(card)
    
    return {"counter_examples": counter_examples}


@router.post("/migration")
async def suggest_migration(
    input_data: MigrationInput,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ModelCard).where(
            ModelCard.id == input_data.model_id,
            ModelCard.user_id == current_user.id
        )
    )
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(status_code=404, detail="Model card not found")
    
    migrations = await model_os_service.suggest_migration(
        model_title=card.title,
        model_concepts=card.examples,
    )
    
    migration_record = {
        "target_domain": input_data.target_domain,
        "suggestions": migrations,
    }
    
    if not card.migration_attempts:
        card.migration_attempts = []
    card.migration_attempts.append(migration_record)
    
    await db.commit()
    await db.refresh(card)
    
    return {"migrations": migrations}
