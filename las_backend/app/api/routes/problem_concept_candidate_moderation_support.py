from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable, Optional

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.entities.user import (
    Concept,
    ConceptAlias,
    ConceptEvidence,
    Problem,
    ProblemConceptCandidate,
)
from app.services.model_os_service import model_os_service

settings = get_settings()


@dataclass(frozen=True)
class ProblemConceptCandidateModerationDeps:
    ensure_concept_record: Callable[..., Awaitable[Optional[Concept]]]
    ensure_concept_relation: Callable[..., Awaitable[None]]
    log_learning_event: Callable[..., Awaitable[None]]


async def load_owned_problem_concept_candidate(
    db: AsyncSession,
    *,
    problem_id: str,
    candidate_id: str,
    user_id: str,
) -> ProblemConceptCandidate:
    candidate_result = await db.execute(
        select(ProblemConceptCandidate)
        .options(selectinload(ProblemConceptCandidate.source_turn))
        .where(
            ProblemConceptCandidate.id == candidate_id,
            ProblemConceptCandidate.problem_id == problem_id,
            ProblemConceptCandidate.user_id == user_id,
        )
    )
    candidate = candidate_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Concept candidate not found")
    return candidate


async def refresh_problem_concept_candidate(
    db: AsyncSession,
    *,
    candidate_id: str,
) -> ProblemConceptCandidate:
    refreshed_result = await db.execute(
        select(ProblemConceptCandidate)
        .options(selectinload(ProblemConceptCandidate.source_turn))
        .where(ProblemConceptCandidate.id == candidate_id)
    )
    return refreshed_result.scalar_one()


async def accept_problem_concept_candidate(
    db: AsyncSession,
    *,
    deps: ProblemConceptCandidateModerationDeps,
    problem: Problem,
    candidate: ProblemConceptCandidate,
    user_id: str,
    trace_id: str,
) -> list[str]:
    candidate.status = "accepted"
    candidate.merged_into_concept = None
    candidate.reviewer_id = user_id
    candidate.reviewed_at = datetime.utcnow()

    existing = model_os_service.normalize_concepts(
        problem.associated_concepts or [],
        limit=max(6, int(settings.PROBLEM_MAX_ASSOCIATED_CONCEPTS)),
    )
    merged = model_os_service.normalize_concepts(
        existing + [candidate.concept_text],
        limit=max(6, int(settings.PROBLEM_MAX_ASSOCIATED_CONCEPTS)),
    )
    accepted_concepts: list[str] = []
    if merged != existing:
        problem.associated_concepts = merged
        model_os_service.refresh_problem_embedding(problem)
        accepted_concepts = [candidate.concept_text]

    anchor_concept = (
        model_os_service.normalize_concepts(problem.associated_concepts or [], limit=1) or [problem.title]
    )[0]
    target_concept = await deps.ensure_concept_record(
        db=db,
        user_id=user_id,
        concept_text=candidate.concept_text,
        source_type="candidate_accept",
        source_id=str(problem.id),
        confidence=float(candidate.confidence or 0.0),
        snippet=candidate.evidence_snippet,
    )
    anchor_record = await deps.ensure_concept_record(
        db=db,
        user_id=user_id,
        concept_text=anchor_concept,
        source_type="candidate_accept",
        source_id=str(problem.id),
        confidence=0.9,
        snippet=candidate.evidence_snippet,
    )
    if anchor_record and target_concept:
        await deps.ensure_concept_relation(
            db=db,
            user_id=user_id,
            source_concept_id=anchor_record.id,
            target_concept_id=target_concept.id,
            relation_type="related",
        )

    await deps.log_learning_event(
        db=db,
        user_id=user_id,
        problem_id=str(problem.id),
        event_type="concept_candidate_accepted",
        learning_mode=candidate.learning_mode,
        trace_id=trace_id,
        payload={
            "candidate_id": str(candidate.id),
            "concept_text": candidate.concept_text,
            "confidence": candidate.confidence,
        },
    )
    return accepted_concepts


async def reject_problem_concept_candidate(
    db: AsyncSession,
    *,
    deps: ProblemConceptCandidateModerationDeps,
    candidate: ProblemConceptCandidate,
    problem_id: str,
    user_id: str,
    trace_id: str,
) -> None:
    candidate.status = "rejected"
    candidate.merged_into_concept = None
    candidate.reviewer_id = user_id
    candidate.reviewed_at = datetime.utcnow()

    await deps.log_learning_event(
        db=db,
        user_id=user_id,
        problem_id=problem_id,
        event_type="concept_candidate_rejected",
        learning_mode=candidate.learning_mode,
        trace_id=trace_id,
        payload={
            "candidate_id": str(candidate.id),
            "concept_text": candidate.concept_text,
            "confidence": candidate.confidence,
        },
    )


async def merge_problem_concept_candidate(
    db: AsyncSession,
    *,
    deps: ProblemConceptCandidateModerationDeps,
    problem: Problem,
    candidate: ProblemConceptCandidate,
    user_id: str,
    target_concept_text: str,
    trace_id: str,
) -> None:
    normalized_target = model_os_service.normalize_concepts([target_concept_text], limit=1)
    if not normalized_target:
        raise HTTPException(status_code=400, detail="Target concept is required")
    target_concept_text = normalized_target[0]
    target_key = model_os_service.normalize_concept_key(target_concept_text)
    if target_key == candidate.normalized_text:
        raise HTTPException(status_code=400, detail="Merge target must be an existing concept")

    existing_problem_targets = {
        model_os_service.normalize_concept_key(item)
        for item in model_os_service.normalize_concepts(
            problem.associated_concepts or [],
            limit=max(6, int(settings.PROBLEM_MAX_ASSOCIATED_CONCEPTS)),
        )
    }
    target_exists = target_key in existing_problem_targets
    if not target_exists:
        concept_result = await db.execute(
            select(Concept).where(
                Concept.user_id == user_id,
                Concept.normalized_name == target_key,
            )
        )
        target_exists = concept_result.scalars().first() is not None
    if not target_exists:
        alias_result = await db.execute(
            select(ConceptAlias)
            .join(Concept, Concept.id == ConceptAlias.concept_id)
            .where(
                Concept.user_id == user_id,
                ConceptAlias.normalized_alias == target_key,
            )
        )
        target_exists = alias_result.scalars().first() is not None
    if not target_exists:
        raise HTTPException(status_code=400, detail="Merge target must already exist")

    target_concept_result = await db.execute(
        select(Concept).where(
            Concept.user_id == user_id,
            Concept.normalized_name == target_key,
        )
    )
    target_concept = target_concept_result.scalars().first()
    if target_concept is None:
        alias_concept_result = await db.execute(
            select(Concept)
            .join(ConceptAlias, Concept.id == ConceptAlias.concept_id)
            .where(
                Concept.user_id == user_id,
                ConceptAlias.normalized_alias == target_key,
            )
        )
        target_concept = alias_concept_result.scalars().first()
    if target_concept is None:
        target_concept = await deps.ensure_concept_record(
            db=db,
            user_id=user_id,
            concept_text=target_concept_text,
            source_type="candidate_merge_target",
            source_id=str(problem.id),
            confidence=max(0.7, float(candidate.confidence or 0.0)),
            snippet=candidate.evidence_snippet,
        )
    if not target_concept:
        raise HTTPException(status_code=400, detail="Failed to resolve merge target")

    alias_result = await db.execute(
        select(ConceptAlias).where(
            ConceptAlias.concept_id == target_concept.id,
            ConceptAlias.normalized_alias == candidate.normalized_text,
        )
    )
    if alias_result.scalars().first() is None:
        db.add(
            ConceptAlias(
                concept_id=target_concept.id,
                alias=candidate.concept_text,
                normalized_alias=candidate.normalized_text,
            )
        )

    db.add(
        ConceptEvidence(
            user_id=user_id,
            concept_id=target_concept.id,
            source_type="candidate_merge",
            source_id=str(problem.id),
            snippet=(candidate.evidence_snippet or "")[:500] or None,
            confidence=max(0.0, min(1.0, float(candidate.confidence or 0.0))),
        )
    )

    canonical_existing = model_os_service.normalize_concepts(
        problem.associated_concepts or [],
        limit=max(6, int(settings.PROBLEM_MAX_ASSOCIATED_CONCEPTS)),
    )
    merged_problem_concepts = model_os_service.normalize_concepts(
        canonical_existing + [target_concept.canonical_name],
        limit=max(6, int(settings.PROBLEM_MAX_ASSOCIATED_CONCEPTS)),
    )
    if merged_problem_concepts != canonical_existing:
        problem.associated_concepts = merged_problem_concepts
        model_os_service.refresh_problem_embedding(problem)

    candidate.status = "merged"
    candidate.merged_into_concept = target_concept.canonical_name
    candidate.reviewer_id = user_id
    candidate.reviewed_at = datetime.utcnow()

    await deps.log_learning_event(
        db=db,
        user_id=user_id,
        problem_id=str(problem.id),
        event_type="concept_candidate_merged",
        learning_mode=candidate.learning_mode,
        trace_id=trace_id,
        payload={
            "candidate_id": str(candidate.id),
            "concept_text": candidate.concept_text,
            "merged_into_concept": target_concept.canonical_name,
            "confidence": candidate.confidence,
        },
    )


async def postpone_problem_concept_candidate(
    db: AsyncSession,
    *,
    deps: ProblemConceptCandidateModerationDeps,
    candidate: ProblemConceptCandidate,
    problem_id: str,
    user_id: str,
    trace_id: str,
) -> None:
    candidate.status = "postponed"
    candidate.merged_into_concept = None
    candidate.reviewer_id = user_id
    candidate.reviewed_at = datetime.utcnow()

    await deps.log_learning_event(
        db=db,
        user_id=user_id,
        problem_id=problem_id,
        event_type="concept_candidate_postponed",
        learning_mode=candidate.learning_mode,
        trace_id=trace_id,
        payload={
            "candidate_id": str(candidate.id),
            "concept_text": candidate.concept_text,
            "confidence": candidate.confidence,
        },
    )


async def rollback_problem_concept(
    db: AsyncSession,
    *,
    deps: ProblemConceptCandidateModerationDeps,
    problem: Problem,
    user_id: str,
    concept_text: str,
    reason: Optional[str],
    trace_id: str,
) -> dict:
    normalized_target = model_os_service.normalize_concept_key(concept_text)
    existing = model_os_service.normalize_concepts(
        problem.associated_concepts or [],
        limit=max(6, int(settings.PROBLEM_MAX_ASSOCIATED_CONCEPTS)),
    )
    kept = [
        item for item in existing
        if model_os_service.normalize_concept_key(item) != normalized_target
    ]
    removed = len(kept) != len(existing)
    if removed:
        problem.associated_concepts = kept
        model_os_service.refresh_problem_embedding(problem)

    await db.execute(
        text(
            """
            UPDATE problem_concept_candidates
            SET status = 'reverted',
                reviewer_id = :reviewer_id,
                reviewed_at = :reviewed_at
            WHERE problem_id = :problem_id
              AND user_id = :user_id
              AND normalized_text = :normalized_text
              AND status = 'accepted'
            """
        ),
        {
            "reviewer_id": user_id,
            "reviewed_at": datetime.utcnow(),
            "problem_id": str(problem.id),
            "user_id": user_id,
            "normalized_text": normalized_target,
        },
    )

    await deps.log_learning_event(
        db=db,
        user_id=user_id,
        problem_id=str(problem.id),
        event_type="concept_rolled_back",
        learning_mode=problem.learning_mode,
        trace_id=trace_id,
        payload={
            "concept_text": concept_text,
            "removed": removed,
            "reason": reason or "",
        },
    )
    return {
        "removed": removed,
        "concept_text": concept_text,
        "associated_concepts": kept if removed else existing,
        "trace_id": trace_id,
    }
