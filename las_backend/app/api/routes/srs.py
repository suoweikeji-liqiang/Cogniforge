"""Spaced Repetition System API routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.entities.user import ModelCard, ProblemConceptCandidate, ReviewSchedule, User
from app.api.routes.auth import get_current_user
from app.services.srs_service import srs_service

router = APIRouter(prefix="/srs", tags=["Spaced Repetition"])


def _build_turn_preview(candidate: ProblemConceptCandidate) -> Optional[str]:
    turn = getattr(candidate, "source_turn", None)
    if turn is None:
        return None

    user_text = str(turn.user_text or "").strip()
    assistant_text = str(turn.assistant_text or "").strip()
    if user_text and assistant_text:
        return f"{user_text[:110]} -> {assistant_text[:110]}"
    if user_text:
        return user_text[:220]
    if assistant_text:
        return assistant_text[:220]
    return None


def _serialize_review_origin(candidate: ProblemConceptCandidate) -> dict:
    problem = getattr(candidate, "problem", None)
    return {
        "source_type": "problem_concept_candidate",
        "problem_id": candidate.problem_id,
        "problem_title": getattr(problem, "title", None),
        "learning_mode": candidate.learning_mode,
        "source_turn_id": candidate.source_turn_id,
        "source_turn_preview": _build_turn_preview(candidate),
        "concept_candidate_id": candidate.id,
        "concept_text": candidate.concept_text,
        "candidate_status": candidate.status,
        "evidence_snippet": candidate.evidence_snippet,
        "reviewed_at": candidate.reviewed_at.isoformat() if candidate.reviewed_at else None,
    }


async def _load_cards(db: AsyncSession, model_card_ids: list[str]) -> dict[str, ModelCard]:
    if not model_card_ids:
        return {}

    result = await db.execute(
        select(ModelCard).where(ModelCard.id.in_(model_card_ids))
    )
    return {
        str(card.id): card
        for card in result.scalars().all()
    }


async def _load_review_origins(
    db: AsyncSession,
    *,
    user_id: str,
    model_card_ids: list[str],
) -> dict[str, dict]:
    if not model_card_ids:
        return {}

    result = await db.execute(
        select(ProblemConceptCandidate)
        .options(
            selectinload(ProblemConceptCandidate.problem),
            selectinload(ProblemConceptCandidate.source_turn),
        )
        .where(
            ProblemConceptCandidate.user_id == user_id,
            ProblemConceptCandidate.linked_model_card_id.in_(model_card_ids),
        )
        .order_by(
            ProblemConceptCandidate.reviewed_at.desc().nullslast(),
            ProblemConceptCandidate.created_at.desc(),
        )
    )

    origins: dict[str, dict] = {}
    for candidate in result.scalars().all():
        model_card_id = str(candidate.linked_model_card_id or "")
        if model_card_id and model_card_id not in origins:
            origins[model_card_id] = _serialize_review_origin(candidate)
    return origins


def _serialize_schedule(schedule: ReviewSchedule, card: ModelCard | None, origin: dict | None) -> dict:
    return {
        "schedule_id": schedule.id,
        "model_card_id": schedule.model_card_id,
        "title": card.title if card else "Unknown",
        "user_notes": card.user_notes if card else None,
        "examples": card.examples or [] if card else [],
        "counter_examples": card.counter_examples or [] if card else [],
        "ease_factor": schedule.ease_factor,
        "interval_days": schedule.interval_days,
        "repetitions": schedule.repetitions,
        "next_review_at": schedule.next_review_at.isoformat(),
        "last_reviewed_at": schedule.last_reviewed_at.isoformat() if schedule.last_reviewed_at else None,
        "origin": origin,
    }


@router.get("/due")
async def get_due_reviews(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get model cards due for review."""
    schedules = await srs_service.get_due_cards(db, str(current_user.id))
    model_card_ids = [str(schedule.model_card_id) for schedule in schedules]
    cards = await _load_cards(db, model_card_ids)
    origins = await _load_review_origins(
        db,
        user_id=str(current_user.id),
        model_card_ids=model_card_ids,
    )

    result = []
    for s in schedules:
        card = cards.get(str(s.model_card_id))
        if card:
            result.append(_serialize_schedule(s, card, origins.get(str(s.model_card_id))))
    return result


@router.post("/schedule/{card_id}")
async def schedule_card(
    card_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a model card to the review schedule."""
    card = await db.get(ModelCard, card_id)
    if not card or card.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Model card not found")

    existing = await db.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.user_id == str(current_user.id),
            ReviewSchedule.model_card_id == card_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Card already scheduled")

    schedule = srs_service.schedule_card(card_id, str(current_user.id))
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return {"id": schedule.id, "next_review_at": schedule.next_review_at.isoformat()}


@router.post("/review/{schedule_id}")
async def submit_review(
    schedule_id: str,
    quality: int = 3,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a review result. quality: 0-5 (0=forgot, 5=perfect)."""
    schedule = await db.get(ReviewSchedule, schedule_id)
    if not schedule or schedule.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Schedule not found")

    schedule = srs_service.process_review(schedule, quality)
    await db.commit()
    await db.refresh(schedule)
    return {
        "schedule_id": schedule.id,
        "next_review_at": schedule.next_review_at.isoformat(),
        "interval_days": schedule.interval_days,
        "ease_factor": schedule.ease_factor,
        "repetitions": schedule.repetitions,
    }


@router.get("/schedules")
async def get_all_schedules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all review schedules for the current user."""
    schedules = await srs_service.get_all_schedules(db, str(current_user.id))
    model_card_ids = [str(schedule.model_card_id) for schedule in schedules]
    cards = await _load_cards(db, model_card_ids)
    origins = await _load_review_origins(
        db,
        user_id=str(current_user.id),
        model_card_ids=model_card_ids,
    )

    result = []
    for s in schedules:
        result.append(
            _serialize_schedule(
                s,
                cards.get(str(s.model_card_id)),
                origins.get(str(s.model_card_id)),
            )
        )
    return result
