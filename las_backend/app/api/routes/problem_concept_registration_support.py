import re
from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities.user import (
    Concept,
    ConceptAlias,
    ConceptEvidence,
    ConceptRelation,
    Problem,
    ProblemConceptCandidate,
    ProblemTurn,
)
from app.services.model_os_service import model_os_service

settings = get_settings()
MAX_CONCEPT_EVIDENCE_SNIPPET_CHARS = 1200

def clamp_concept_evidence_snippet(text: Optional[str], limit: int = MAX_CONCEPT_EVIDENCE_SNIPPET_CHARS) -> str:
    source = str(text or "").strip()
    if not source:
        return ""
    normalized = re.sub(r"\r\n?", "\n", source)
    if len(normalized) <= limit:
        return normalized

    floor = max(120, int(limit * 0.45))
    boundary_positions = [
        normalized.rfind(marker, floor, limit)
        for marker in ("\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", "；", ";")
    ]
    boundary = max(boundary_positions)
    if boundary != -1:
        snippet = normalized[:boundary].rstrip()
    else:
        snippet = normalized[:limit].rstrip()
    return f"{snippet}..."


def build_concept_evidence_snippet(user_text: str, anchor_text: str) -> str:
    source = "\n".join([str(user_text or "").strip(), str(anchor_text or "").strip()]).strip()
    if not source:
        return ""
    return clamp_concept_evidence_snippet(source)


def estimate_concept_confidence(
    concept: str,
    *,
    anchor_concept: str,
    user_text: str,
    retrieval_context: Optional[str],
) -> float:
    normalized = model_os_service.normalize_concept_key(concept)
    if not normalized:
        return 0.0

    score = 0.62
    anchor_normalized = model_os_service.normalize_concept_key(anchor_concept)
    if normalized == anchor_normalized:
        score += 0.28

    text_blob = " ".join([str(user_text or ""), str(retrieval_context or "")]).casefold()
    if normalized and normalized in text_blob:
        score += 0.08

    token_count = len(normalized.split())
    if token_count <= 5:
        score += 0.04

    return round(max(0.0, min(0.99, score)), 4)


async def ensure_concept_record(
    db: AsyncSession,
    *,
    user_id: str,
    concept_text: str,
    source_type: str,
    source_id: Optional[str],
    confidence: float,
    snippet: Optional[str],
) -> Optional[Concept]:
    normalized = model_os_service.normalize_concept_key(concept_text)
    if not normalized:
        return None
    cleaned_name = model_os_service.normalize_concepts([concept_text], limit=1)
    if not cleaned_name:
        return None
    display_name = cleaned_name[0]

    concept_result = await db.execute(
        select(Concept).where(
            Concept.user_id == user_id,
            Concept.normalized_name == normalized,
        )
    )
    concept = concept_result.scalars().first()
    if concept is None:
        concept = Concept(
            user_id=user_id,
            canonical_name=display_name,
            normalized_name=normalized,
            language="auto",
            status="active",
        )
        db.add(concept)
        await db.flush()

    alias_result = await db.execute(
        select(ConceptAlias).where(
            ConceptAlias.concept_id == concept.id,
            ConceptAlias.normalized_alias == normalized,
        )
    )
    if alias_result.scalars().first() is None:
        db.add(
            ConceptAlias(
                concept_id=concept.id,
                alias=display_name,
                normalized_alias=normalized,
            )
        )

    db.add(
        ConceptEvidence(
            user_id=user_id,
            concept_id=concept.id,
            source_type=source_type,
            source_id=source_id,
            snippet=clamp_concept_evidence_snippet(snippet) or None,
            confidence=max(0.0, min(1.0, float(confidence or 0.0))),
        )
    )
    return concept


async def ensure_concept_relation(
    db: AsyncSession,
    *,
    user_id: str,
    source_concept_id: str,
    target_concept_id: str,
    relation_type: str = "related",
) -> None:
    if source_concept_id == target_concept_id:
        return
    existing = await db.execute(
        select(ConceptRelation).where(
            ConceptRelation.user_id == user_id,
            ConceptRelation.source_concept_id == source_concept_id,
            ConceptRelation.target_concept_id == target_concept_id,
            ConceptRelation.relation_type == relation_type,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return
    db.add(
        ConceptRelation(
            user_id=user_id,
            source_concept_id=source_concept_id,
            target_concept_id=target_concept_id,
            relation_type=relation_type,
            weight=1.0,
            version=1,
        )
    )


async def register_problem_concept_candidates(
    db: AsyncSession,
    *,
    user_id: str,
    problem: Problem,
    learning_mode: str,
    source_turn_id: Optional[str],
    source_path_id: Optional[str],
    inferred_concepts: List[str],
    source: str,
    anchor_concept: str,
    user_text: str,
    retrieval_context: Optional[str],
    evidence_snippet: str,
) -> tuple[List[str], List[str]]:
    max_candidates = max(1, int(settings.PROBLEM_CONCEPT_MAX_CANDIDATES_PER_TURN))
    max_concepts = max(6, int(settings.PROBLEM_MAX_ASSOCIATED_CONCEPTS))
    auto_accept_threshold = max(0.0, min(1.0, float(settings.PROBLEM_CONCEPT_AUTO_ACCEPT_CONFIDENCE)))

    normalized_inputs = model_os_service.filter_low_signal_concepts(inferred_concepts, limit=max_candidates)
    if not normalized_inputs:
        return [], []

    existing_concepts = model_os_service.normalize_concepts(problem.associated_concepts or [], limit=max_concepts)
    existing_keys = {model_os_service.normalize_concept_key(item) for item in existing_concepts}

    existing_candidate_rows = await db.execute(
        select(ProblemConceptCandidate.normalized_text, ProblemTurn.path_id)
        .outerjoin(ProblemTurn, ProblemTurn.id == ProblemConceptCandidate.source_turn_id)
        .where(
            ProblemConceptCandidate.problem_id == str(problem.id),
            ProblemConceptCandidate.user_id == user_id,
            ProblemConceptCandidate.status.in_(["pending", "accepted", "merged"]),
        )
    )
    existing_candidate_contexts = {
        (str(row[0] or ""), str(row[1]) if row[1] else None)
        for row in existing_candidate_rows.all()
    }

    accepted_concepts: List[str] = []
    pending_concepts: List[str] = []
    accepted_concept_ids: List[str] = []

    anchor_record = await ensure_concept_record(
        db=db,
        user_id=user_id,
        concept_text=anchor_concept,
        source_type=source,
        source_id=str(problem.id),
        confidence=0.95,
        snippet=evidence_snippet,
    )

    for concept in normalized_inputs:
        normalized = model_os_service.normalize_concept_key(concept)
        if not normalized:
            continue
        has_same_path_candidate = False
        if source_path_id:
            has_same_path_candidate = (normalized, source_path_id) in existing_candidate_contexts
        else:
            has_same_path_candidate = any(
                candidate_key == normalized
                for candidate_key, _candidate_path_id in existing_candidate_contexts
            )

        allow_path_context_duplicate = bool(
            source_path_id
            and not has_same_path_candidate
            and (
                normalized in existing_keys
                or any(candidate_key == normalized for candidate_key, _candidate_path_id in existing_candidate_contexts)
            )
        )

        if has_same_path_candidate or (
            not allow_path_context_duplicate
            and (normalized in existing_keys or any(candidate_key == normalized for candidate_key, _candidate_path_id in existing_candidate_contexts))
        ):
            continue

        confidence = estimate_concept_confidence(
            concept,
            anchor_concept=anchor_concept,
            user_text=user_text,
            retrieval_context=retrieval_context,
        )
        status = "accepted" if confidence >= auto_accept_threshold else "pending"
        db.add(
            ProblemConceptCandidate(
                user_id=user_id,
                problem_id=str(problem.id),
                concept_text=concept,
                normalized_text=normalized,
                source=source,
                learning_mode=learning_mode,
                source_turn_id=source_turn_id,
                confidence=confidence,
                status=status,
                evidence_snippet=clamp_concept_evidence_snippet(evidence_snippet) or None,
            )
        )
        existing_candidate_contexts.add((normalized, source_path_id or None))

        if status == "accepted":
            accepted_concepts.append(concept)
            concept_record = await ensure_concept_record(
                db=db,
                user_id=user_id,
                concept_text=concept,
                source_type=source,
                source_id=str(problem.id),
                confidence=confidence,
                snippet=evidence_snippet,
            )
            if concept_record:
                accepted_concept_ids.append(str(concept_record.id))
                if normalized not in existing_keys:
                    existing_keys.add(normalized)
                    if len(existing_concepts) < max_concepts:
                        existing_concepts.append(concept_record.canonical_name)
        else:
            pending_concepts.append(concept)

    if accepted_concepts:
        problem.associated_concepts = model_os_service.normalize_concepts(
            [*existing_concepts, *accepted_concepts],
            limit=max_concepts,
        )

    if anchor_record and accepted_concept_ids:
        for concept_id in accepted_concept_ids:
            await ensure_concept_relation(
                db=db,
                user_id=user_id,
                source_concept_id=str(anchor_record.id),
                target_concept_id=concept_id,
                relation_type="related",
            )

    return accepted_concepts, pending_concepts
