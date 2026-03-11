from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from typing import List, Optional

from app.core.database import get_db
from app.models.entities.user import User, ModelCard, EvolutionLog, ReviewSchedule
from app.schemas.model_card import (
    ModelCardCreate,
    ModelCardListResponse,
    ModelCardUpdate,
    ModelCardResponse,
    CounterExampleInput,
    MigrationInput,
    EvolutionCompare,
    EvolutionLogResponse,
)
from app.api.routes.auth import get_current_user
from app.api.routes.srs import _load_review_origins, _serialize_schedule
from app.services.model_os_service import model_os_service

router = APIRouter(prefix="/model-cards", tags=["Model Cards"])


def merge_ranked_cards(primary_cards: List[ModelCard], fallback_cards: List[ModelCard]) -> List[ModelCard]:
    merged: List[ModelCard] = []
    seen: set[str] = set()
    for card in primary_cards + fallback_cards:
        card_id = str(card.id)
        if card_id in seen:
            continue
        seen.add(card_id)
        merged.append(card)
    return merged


async def rank_model_cards_with_backend(
    db: AsyncSession,
    current_user: User,
    cards: List[ModelCard],
    query: str,
) -> List[ModelCard]:
    bind = db.get_bind()
    fallback_ranked_cards = model_os_service.rank_model_cards(cards, query)

    if not (bind and bind.dialect.name == "postgresql" and cards):
        return fallback_ranked_cards

    query_embedding = model_os_service.generate_embedding(query)
    embedding_param = model_os_service.serialize_embedding_for_pgvector(query_embedding)
    native_rank_result = await db.execute(
        text(
            """
            SELECT mc.id
            FROM model_cards mc
            WHERE mc.user_id = :user_id
              AND mc.embedding IS NOT NULL
              AND mc.id = ANY(:card_ids)
            ORDER BY mc.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        ),
        {
            "user_id": str(current_user.id),
            "card_ids": [str(card.id) for card in cards],
            "embedding": embedding_param,
            "limit": max(len(cards), 1),
        },
    )
    card_map = {str(card.id): card for card in cards}
    native_ranked_cards = [
        card_map[row[0]]
        for row in native_rank_result.all()
        if row[0] in card_map
    ]
    return merge_ranked_cards(native_ranked_cards, fallback_ranked_cards)


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
    
    examples = card_data.examples or model_data.get("examples", [])
    counter_examples = model_data.get("limitations", [])

    db_card = ModelCard(
        user_id=current_user.id,
        title=card_data.title,
        lifecycle_stage="draft",
        origin_type="manual",
        origin_stage="manual_creation",
        concept_maps=model_data.get("concept_maps"),
        user_notes=card_data.user_notes,
        examples=examples,
        counter_examples=counter_examples,
        embedding=model_os_service.generate_card_embedding(
            title=card_data.title,
            user_notes=card_data.user_notes,
            examples=examples,
            counter_examples=counter_examples,
        ),
    )
    
    db.add(db_card)
    await db.commit()
    await db.refresh(db_card)

    await model_os_service.log_evolution(
        db=db,
        model_id=str(db_card.id),
        user_id=str(current_user.id),
        action="create",
        reason="Model card created",
        snapshot=model_os_service.build_model_snapshot(db_card),
    )

    return db_card


@router.get("/", response_model=List[ModelCardListResponse])
async def list_model_cards(
    q: Optional[str] = Query(default=None),
    scheduled: Optional[bool] = Query(default=None),
    limit: int = Query(default=12, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ModelCard)
        .where(ModelCard.user_id == current_user.id)
        .order_by(ModelCard.created_at.desc())
    )
    cards = list(result.scalars().all())

    if scheduled is not None:
        schedules_result = await db.execute(
            select(ReviewSchedule.model_card_id).where(
                ReviewSchedule.user_id == str(current_user.id)
            )
        )
        scheduled_ids = {row[0] for row in schedules_result.all()}
        cards = [
            card for card in cards
            if (str(card.id) in scheduled_ids) == scheduled
        ]

    if q:
        cards = await rank_model_cards_with_backend(db, current_user, cards, q)

    page_cards = cards[offset:offset + limit]
    card_ids = [str(card.id) for card in page_cards]
    schedules_by_card_id: dict[str, dict] = {}

    if card_ids:
        schedules_result = await db.execute(
            select(ReviewSchedule).where(
                ReviewSchedule.user_id == str(current_user.id),
                ReviewSchedule.model_card_id.in_(card_ids),
            )
        )
        schedule_rows = list(schedules_result.scalars().all())
        origins = await _load_review_origins(
            db,
            user_id=str(current_user.id),
            model_card_ids=card_ids,
        )
        card_map = {str(card.id): card for card in page_cards}
        schedules_by_card_id = {
            str(schedule.model_card_id): _serialize_schedule(
                schedule,
                card_map.get(str(schedule.model_card_id)),
                origins.get(str(schedule.model_card_id)),
            )
            for schedule in schedule_rows
        }

    payload: List[dict] = []
    for card in page_cards:
        card_body = ModelCardResponse.model_validate(card).model_dump()
        review_schedule = schedules_by_card_id.get(str(card.id))
        payload.append(
            {
                **card_body,
                "is_scheduled": review_schedule is not None,
                "review_schedule": review_schedule,
            }
        )
    return payload


@router.get("/{card_id}/similar", response_model=List[ModelCardResponse])
async def list_similar_model_cards(
    card_id: UUID,
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ModelCard).where(
            ModelCard.id == str(card_id),
            ModelCard.user_id == str(current_user.id),
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Model card not found")

    all_cards_result = await db.execute(
        select(ModelCard)
        .where(
            ModelCard.user_id == str(current_user.id),
            ModelCard.id != str(card_id),
        )
        .order_by(ModelCard.updated_at.desc())
    )
    candidate_cards = list(all_cards_result.scalars().all())
    query = model_os_service.build_embedding_text(
        title=card.title,
        user_notes=card.user_notes,
        examples=card.examples,
        counter_examples=card.counter_examples,
    )
    ranked_cards = await rank_model_cards_with_backend(db, current_user, candidate_cards, query)
    return ranked_cards[:limit]


@router.get("/{card_id}", response_model=ModelCardResponse)
async def get_model_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ModelCard).where(
            ModelCard.id == str(card_id),
            ModelCard.user_id == str(current_user.id)
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
            ModelCard.id == str(card_id),
            ModelCard.user_id == str(current_user.id)
        )
    )
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(status_code=404, detail="Model card not found")
    
    if card_data.title is not None:
        card.title = card_data.title
    if card_data.concept_maps is not None:
        card.concept_maps = card_data.concept_maps
    if card_data.user_notes is not None:
        card.user_notes = card_data.user_notes
    if card_data.examples is not None:
        card.examples = card_data.examples
    if card_data.counter_examples is not None:
        card.counter_examples = card_data.counter_examples
    if card_data.migration_attempts is not None:
        card.migration_attempts = card_data.migration_attempts

    card.version += 1
    model_os_service.refresh_card_embedding(card)

    await model_os_service.log_evolution(
        db=db,
        model_id=str(card.id),
        user_id=str(current_user.id),
        action="update",
        reason=card_data.change_reason or "Model card updated",
        snapshot=model_os_service.build_model_snapshot(card),
    )

    await db.commit()
    await db.refresh(card)

    return card


@router.post("/{card_id}/activate", response_model=ModelCardResponse)
async def activate_model_card(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ModelCard).where(
            ModelCard.id == str(card_id),
            ModelCard.user_id == str(current_user.id)
        )
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Model card not found")

    notes = str(card.user_notes or "").strip()
    examples = [str(example).strip() for example in (card.examples or []) if str(example).strip()]
    if not notes and not examples:
        raise HTTPException(
            status_code=400,
            detail="Draft needs notes or examples before it can enter the review lifecycle",
        )

    if card.lifecycle_stage != "active":
        card.lifecycle_stage = "active"
        card.version += 1
        model_os_service.refresh_card_embedding(card)

        await model_os_service.log_evolution(
            db=db,
            model_id=str(card.id),
            user_id=str(current_user.id),
            action="activate",
            reason="Manual draft marked ready for review",
            snapshot=model_os_service.build_model_snapshot(card),
        )

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
            ModelCard.id == str(card_id),
            ModelCard.user_id == str(current_user.id)
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
            ModelCard.id == str(input_data.model_id),
            ModelCard.user_id == str(current_user.id)
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
    model_os_service.refresh_card_embedding(card)

    await model_os_service.log_evolution(
        db=db,
        model_id=str(card.id),
        user_id=str(current_user.id),
        action="counter_examples",
        reason="Counter examples generated",
        snapshot=model_os_service.build_model_snapshot(card),
    )

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
    model_os_service.refresh_card_embedding(card)

    await model_os_service.log_evolution(
        db=db,
        model_id=str(card.id),
        user_id=str(current_user.id),
        action="migration",
        reason=f"Cross-domain migration to {input_data.target_domain}",
        snapshot=model_os_service.build_model_snapshot(card),
    )

    await db.commit()
    await db.refresh(card)

    return {"migrations": migrations}


@router.get("/{card_id}/evolution", response_model=List[EvolutionLogResponse])
async def get_evolution_logs(
    card_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get evolution timeline for a model card."""
    result = await db.execute(
        select(ModelCard).where(
            ModelCard.id == str(card_id),
            ModelCard.user_id == str(current_user.id),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Model card not found")

    logs = await db.execute(
        select(EvolutionLog)
        .where(EvolutionLog.model_id == str(card_id))
        .order_by(EvolutionLog.created_at.asc())
    )
    return list(logs.scalars().all())


@router.get("/{card_id}/compare", response_model=EvolutionCompare)
async def compare_evolution_versions(
    card_id: str,
    from_log_id: Optional[str] = Query(default=None),
    to_log_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ModelCard).where(
            ModelCard.id == str(card_id),
            ModelCard.user_id == str(current_user.id),
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Model card not found")

    logs_result = await db.execute(
        select(EvolutionLog)
        .where(EvolutionLog.model_id == str(card_id))
        .order_by(EvolutionLog.created_at.asc())
    )
    logs = [log for log in logs_result.scalars().all() if log.snapshot]
    if not logs:
        raise HTTPException(status_code=404, detail="No version history available")

    logs_by_id = {str(log.id): log for log in logs}

    to_log = logs[-1]
    if to_log_id:
        to_log = logs_by_id.get(str(to_log_id))
        if not to_log:
            raise HTTPException(status_code=404, detail="Target version not found")

    from_log = None
    if from_log_id:
        from_log = logs_by_id.get(str(from_log_id))
        if not from_log:
            raise HTTPException(status_code=404, detail="Source version not found")
    else:
        to_index = logs.index(to_log)
        if to_index > 0:
            from_log = logs[to_index - 1]

    summary = await model_os_service.generate_evolution_summary(
        card_title=card.title,
        old_snapshot=from_log.snapshot if from_log else None,
        new_snapshot=to_log.snapshot,
    )

    return {
        "old_version": from_log.snapshot if from_log else None,
        "new_version": to_log.snapshot,
        "changes_summary": summary,
    }
