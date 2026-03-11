"""Spaced Repetition System API routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.entities.user import ModelCard, ProblemConceptCandidate, ProblemTurn, ReviewSchedule, User
from app.api.routes.auth import get_current_user
from app.services.model_os_service import model_os_service
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


def _extract_turn_step_concept(candidate: ProblemConceptCandidate) -> Optional[str]:
    turn = getattr(candidate, "source_turn", None)
    if turn is None:
        return None

    metadata = getattr(turn, "mode_metadata", None) or {}
    step_concept = str(metadata.get("step_concept") or "").strip()
    if step_concept:
        return step_concept

    problem = getattr(candidate, "problem", None)
    fallback = str(getattr(problem, "title", "") or "").strip()
    return fallback or None


def _serialize_turn_path(candidate: ProblemConceptCandidate) -> dict:
    turn = getattr(candidate, "source_turn", None)
    path = getattr(turn, "learning_path", None) if turn is not None else None
    if path is None:
        return {
            "source_path_id": None,
            "source_path_kind": None,
            "source_path_title": None,
        }

    return {
        "source_path_id": str(path.id),
        "source_path_kind": str(path.kind or "main"),
        "source_path_title": path.title,
    }


def _serialize_review_origin(candidate: ProblemConceptCandidate) -> dict:
    problem = getattr(candidate, "problem", None)
    path_context = _serialize_turn_path(candidate)
    return {
        "source_type": "problem_concept_candidate",
        "problem_id": candidate.problem_id,
        "problem_title": getattr(problem, "title", None),
        "learning_mode": candidate.learning_mode,
        "source_turn_id": candidate.source_turn_id,
        "source_turn_preview": _build_turn_preview(candidate),
        "source_step_index": getattr(getattr(candidate, "source_turn", None), "step_index", None),
        "source_step_concept": _extract_turn_step_concept(candidate),
        **path_context,
        "concept_candidate_id": candidate.id,
        "concept_text": candidate.concept_text,
        "candidate_status": candidate.status,
        "evidence_snippet": candidate.evidence_snippet,
        "reviewed_at": candidate.reviewed_at.isoformat() if candidate.reviewed_at else None,
    }


def _derive_recall_feedback(schedule: ReviewSchedule) -> dict:
    if schedule.last_reviewed_at is None:
        return {
            "recall_state": "scheduled",
            "recent_outcome": "pending",
            "recommended_action": "complete_first_recall",
        }

    if schedule.repetitions == 0:
        return {
            "recall_state": "fragile",
            "recent_outcome": "struggled",
            "recommended_action": "revisit_workspace",
        }

    if schedule.repetitions <= 1 or schedule.interval_days <= 1:
        return {
            "recall_state": "rebuilding",
            "recent_outcome": "held_with_effort",
            "recommended_action": "reinforce_soon",
        }

    if schedule.repetitions < 3 or schedule.interval_days < 7:
        return {
            "recall_state": "reinforcing",
            "recent_outcome": "held",
            "recommended_action": "keep_spacing",
        }

    return {
        "recall_state": "stable",
        "recent_outcome": "strong",
        "recommended_action": "extend_or_compare",
    }


def _build_reinforcement_target(
    *,
    schedule: ReviewSchedule,
    card: ModelCard | None,
    origin: dict | None,
) -> Optional[dict]:
    recall_feedback = _derive_recall_feedback(schedule)
    if recall_feedback["recall_state"] not in {"fragile", "rebuilding"}:
        return None

    concept_text = None
    if origin:
        concept_text = origin.get("concept_text")
    if not concept_text and card:
        concept_text = card.title

    return {
        "status": "needs_reinforcement",
        "priority": "high" if recall_feedback["recall_state"] == "fragile" else "medium",
        "recall_state": recall_feedback["recall_state"],
        "recommended_action": recall_feedback["recommended_action"],
        "problem_id": origin.get("problem_id") if origin else None,
        "problem_title": origin.get("problem_title") if origin else None,
        "concept_text": concept_text,
        "concept_candidate_id": origin.get("concept_candidate_id") if origin else None,
        "source_turn_id": origin.get("source_turn_id") if origin else None,
        "source_turn_preview": origin.get("source_turn_preview") if origin else None,
        "resume_step_index": origin.get("source_step_index") if origin else None,
        "resume_step_concept": origin.get("source_step_concept") if origin else None,
        "resume_path_id": origin.get("source_path_id") if origin else None,
        "resume_path_kind": origin.get("source_path_kind") if origin else None,
        "resume_path_title": origin.get("source_path_title") if origin else None,
    }


async def _log_reinforcement_evolution(
    *,
    db: AsyncSession,
    card: ModelCard | None,
    current_user: User,
    reinforcement_target: dict | None,
) -> None:
    if not card or not reinforcement_target:
        return

    concept_label = reinforcement_target.get("concept_text") or card.title
    workspace_label = reinforcement_target.get("problem_title")
    step_concept = reinforcement_target.get("resume_step_concept")
    path_title = reinforcement_target.get("resume_path_title")
    reason_parts = [f"Weak recall signaled reinforcement for '{concept_label}'."]
    if workspace_label:
        reason_parts.append(f"Return to workspace '{workspace_label}'.")
    if path_title:
        reason_parts.append(f"Resume in path '{path_title}'.")
    if step_concept:
        reason_parts.append(f"Resume near '{step_concept}'.")
    reason_parts.append("Use the learning workspace to rebuild the concept before pushing further.")
    reason = " ".join(reason_parts)

    await model_os_service.log_evolution(
        db=db,
        model_id=str(card.id),
        user_id=str(current_user.id),
        action="recall_reinforcement",
        reason=reason,
        snapshot=model_os_service.build_model_snapshot(card),
    )


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
            selectinload(ProblemConceptCandidate.source_turn).selectinload(ProblemTurn.learning_path),
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
    recall_feedback = _derive_recall_feedback(schedule)
    reinforcement_target = _build_reinforcement_target(
        schedule=schedule,
        card=card,
        origin=origin,
    )
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
        "needs_reinforcement": reinforcement_target is not None,
        "reinforcement_target": reinforcement_target,
        **recall_feedback,
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
    if str(card.lifecycle_stage or "active") != "active":
        raise HTTPException(
            status_code=400,
            detail="Draft model card must be marked ready before it can be scheduled",
        )

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
    card = await db.get(ModelCard, schedule.model_card_id)
    origins = await _load_review_origins(
        db,
        user_id=str(current_user.id),
        model_card_ids=[str(schedule.model_card_id)],
    )
    origin = origins.get(str(schedule.model_card_id))
    recall_feedback = _derive_recall_feedback(schedule)
    reinforcement_target = _build_reinforcement_target(
        schedule=schedule,
        card=card,
        origin=origin,
    )
    if reinforcement_target is not None:
        await _log_reinforcement_evolution(
            db=db,
            card=card,
            current_user=current_user,
            reinforcement_target=reinforcement_target,
        )
    return {
        "schedule_id": schedule.id,
        "quality": quality,
        "next_review_at": schedule.next_review_at.isoformat(),
        "interval_days": schedule.interval_days,
        "ease_factor": schedule.ease_factor,
        "repetitions": schedule.repetitions,
        "origin": origin,
        "needs_reinforcement": reinforcement_target is not None,
        "reinforcement_target": reinforcement_target,
        **recall_feedback,
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
