"""Spaced Repetition System API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.core.database import get_db
from app.models.entities.user import User, ModelCard, ReviewSchedule
from app.api.routes.auth import get_current_user
from app.services.srs_service import srs_service

router = APIRouter(prefix="/srs", tags=["Spaced Repetition"])


@router.get("/due")
async def get_due_reviews(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get model cards due for review."""
    schedules = await srs_service.get_due_cards(db, str(current_user.id))
    result = []
    for s in schedules:
        card = await db.get(ModelCard, s.model_card_id)
        if card:
            result.append({
                "schedule_id": s.id,
                "model_card_id": s.model_card_id,
                "title": card.title,
                "user_notes": card.user_notes,
                "examples": card.examples or [],
                "counter_examples": card.counter_examples or [],
                "ease_factor": s.ease_factor,
                "interval_days": s.interval_days,
                "repetitions": s.repetitions,
                "next_review_at": s.next_review_at.isoformat(),
            })
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
    result = []
    for s in schedules:
        card = await db.get(ModelCard, s.model_card_id)
        result.append({
            "schedule_id": s.id,
            "model_card_id": s.model_card_id,
            "title": card.title if card else "Unknown",
            "user_notes": card.user_notes if card else None,
            "examples": card.examples if card else [],
            "counter_examples": card.counter_examples if card else [],
            "ease_factor": s.ease_factor,
            "interval_days": s.interval_days,
            "repetitions": s.repetitions,
            "next_review_at": s.next_review_at.isoformat(),
            "last_reviewed_at": s.last_reviewed_at.isoformat() if s.last_reviewed_at else None,
        })
    return result
