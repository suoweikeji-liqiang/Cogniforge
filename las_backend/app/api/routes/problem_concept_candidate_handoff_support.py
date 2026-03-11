from typing import Callable, Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities.user import ModelCard, Problem, ProblemConceptCandidate, ReviewSchedule
from app.services.model_os_service import model_os_service
from app.services.srs_service import srs_service


def _candidate_model_card_title(candidate: ProblemConceptCandidate) -> str:
    return str(candidate.merged_into_concept or candidate.concept_text or "").strip()


def _candidate_model_card_origin_stage(candidate: ProblemConceptCandidate) -> str:
    if str(candidate.status or "").strip() == "merged":
        return "merged_concept_candidate"
    return "accepted_concept_candidate"


def _candidate_model_card_notes(
    problem: Problem,
    candidate: ProblemConceptCandidate,
    *,
    build_turn_preview: Callable[[object], Optional[str]],
    normalize_learning_mode: Callable[[Optional[str], str], str],
) -> str:
    title = _candidate_model_card_title(candidate)
    source_turn_preview = build_turn_preview(getattr(candidate, "source_turn", None))
    lines = [
        f"Promoted from problem: {problem.title}",
        f"Source learning mode: {normalize_learning_mode(candidate.learning_mode, 'socratic')}",
    ]
    if source_turn_preview:
        lines.append(f"Source turn: {source_turn_preview}")
    if candidate.evidence_snippet:
        lines.append(f"Evidence: {candidate.evidence_snippet}")
    lines.append(f"Promoted concept: {title}")
    return "\n".join(lines)


async def load_candidate_review_schedule(
    db: AsyncSession,
    *,
    user_id: str,
    model_card_id: str,
) -> Optional[ReviewSchedule]:
    schedule_result = await db.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.user_id == user_id,
            ReviewSchedule.model_card_id == model_card_id,
        )
    )
    return schedule_result.scalar_one_or_none()


async def ensure_model_card_for_candidate(
    db: AsyncSession,
    *,
    user_id: str,
    problem: Problem,
    candidate: ProblemConceptCandidate,
    build_turn_preview: Callable[[object], Optional[str]],
    normalize_learning_mode: Callable[[Optional[str], str], str],
) -> tuple[ModelCard, bool]:
    if candidate.linked_model_card_id:
        linked_card = await db.get(ModelCard, candidate.linked_model_card_id)
        if linked_card and linked_card.user_id == user_id:
            return linked_card, False

    target_title = _candidate_model_card_title(candidate)
    if not target_title:
        raise HTTPException(status_code=400, detail="Candidate cannot be promoted without a concept title")

    existing_result = await db.execute(
        select(ModelCard).where(
            ModelCard.user_id == user_id,
            func.lower(ModelCard.title) == target_title.casefold(),
        )
    )
    existing_card = existing_result.scalar_one_or_none()
    if existing_card:
        if existing_card.lifecycle_stage != "active":
            existing_card.lifecycle_stage = "active"
        candidate.linked_model_card_id = str(existing_card.id)
        await db.flush()
        return existing_card, False

    notes = _candidate_model_card_notes(
        problem,
        candidate,
        build_turn_preview=build_turn_preview,
        normalize_learning_mode=normalize_learning_mode,
    )
    examples = model_os_service.normalize_concepts(
        [candidate.concept_text, problem.title, *(problem.associated_concepts or [])],
        limit=3,
    )
    model_card = ModelCard(
        user_id=user_id,
        title=target_title,
        lifecycle_stage="active",
        origin_type="problem_concept_candidate",
        origin_stage=_candidate_model_card_origin_stage(candidate),
        origin_problem_id=str(problem.id),
        origin_problem_title=problem.title,
        origin_concept_candidate_id=str(candidate.id),
        origin_source_turn_id=str(candidate.source_turn_id) if candidate.source_turn_id else None,
        origin_learning_mode=normalize_learning_mode(candidate.learning_mode, "socratic"),
        origin_concept_text=candidate.concept_text,
        user_notes=notes,
        examples=examples,
        counter_examples=[],
        concept_maps=None,
        embedding=model_os_service.generate_card_embedding(
            title=target_title,
            user_notes=notes,
            examples=examples,
            counter_examples=[],
        ),
    )
    db.add(model_card)
    await db.flush()

    await model_os_service.log_evolution(
        db=db,
        model_id=str(model_card.id),
        user_id=user_id,
        action="create",
        reason="Promoted from derived concept candidate",
        snapshot=model_os_service.build_model_snapshot(model_card),
    )

    candidate.linked_model_card_id = str(model_card.id)
    await db.flush()
    return model_card, True


async def ensure_candidate_review_schedule(
    db: AsyncSession,
    *,
    user_id: str,
    model_card_id: str,
) -> ReviewSchedule:
    review_schedule = await load_candidate_review_schedule(
        db=db,
        user_id=user_id,
        model_card_id=model_card_id,
    )
    if review_schedule is None:
        review_schedule = srs_service.schedule_card(model_card_id, user_id)
        db.add(review_schedule)
        await db.flush()
    return review_schedule


def serialize_problem_concept_candidate_handoff(
    *,
    candidate_payload: dict,
    model_card: ModelCard,
    created_model_card: bool,
    review_schedule: Optional[ReviewSchedule],
    trace_id: str,
) -> dict:
    return {
        "candidate": candidate_payload,
        "model_card": model_card,
        "created_model_card": created_model_card,
        "review_scheduled": review_schedule is not None,
        "next_review_at": review_schedule.next_review_at.isoformat() if review_schedule else None,
        "trace_id": trace_id,
    }
