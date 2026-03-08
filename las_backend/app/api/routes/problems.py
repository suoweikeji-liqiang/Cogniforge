import asyncio
import time
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, desc
from uuid import UUID
from typing import List, Optional

from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities.user import (
    User,
    Problem,
    LearningPath,
    ProblemResponse as ProblemResponseModel,
    ProblemTurn,
    ProblemMasteryEvent,
    ProblemConceptCandidate,
    LearningEvent,
    Concept,
    ConceptAlias,
    ConceptEvidence,
    ConceptRelation,
)
from app.schemas.problem import (
    ProblemCreate,
    ProblemUpdate,
    ProblemResponse,
    ProblemResponseCreate,
    ProblemResponseResponse,
    LearningPathResponse,
    LearningPathProgressUpdate,
    LearningStepHintResponse,
    LearningQuestionRequest,
    LearningQuestionResponse,
    ProblemTurnResponse,
    ProblemConceptCandidateResponse,
    ProblemConceptCandidateActionResponse,
    ProblemConceptRollbackRequest,
    ProblemConceptRollbackResponse,
)
from app.api.routes.auth import get_current_user
from app.services.model_os_service import model_os_service

router = APIRouter(prefix="/problems", tags=["Problems"])
settings = get_settings()


def _resolve_current_step(learning_path: Optional[LearningPath]) -> tuple[int, Optional[dict]]:
    if not learning_path or not isinstance(learning_path.path_data, list) or not learning_path.path_data:
        return 0, None

    current_step_index = min(
        max(int(learning_path.current_step or 0), 0),
        len(learning_path.path_data) - 1,
    )
    step_candidate = learning_path.path_data[current_step_index]
    if not isinstance(step_candidate, dict):
        return current_step_index, None
    return current_step_index, step_candidate


def _should_auto_advance(structured_feedback: dict, mode: str) -> bool:
    verdict = str((structured_feedback or {}).get("correctness", "")).strip().lower()
    if not verdict:
        return False

    negative_markers = ["incorrect", "not correct", "wrong", "错误", "不正确"]
    if any(marker in verdict for marker in negative_markers):
        return False

    partial_markers = [
        "partially correct",
        "mostly correct",
        "基本正确",
        "部分正确",
        "较为正确",
    ]
    full_markers = [
        "correct",
        "正确",
    ]
    has_partial = any(marker in verdict for marker in partial_markers)
    has_full = any(marker in verdict for marker in full_markers) and not has_partial

    misconceptions = (structured_feedback or {}).get("misconceptions") or []
    misconception_count = len([item for item in misconceptions if str(item).strip()])

    normalized_mode = (mode or "balanced").strip().lower()
    if normalized_mode not in {"conservative", "balanced", "aggressive"}:
        normalized_mode = "balanced"

    if normalized_mode == "conservative":
        return has_full and misconception_count == 0
    if normalized_mode == "aggressive":
        return has_full or has_partial

    # balanced
    if has_full:
        return misconception_count <= 1
    if has_partial:
        return misconception_count == 0
    return False


def _normalize_answer_mode(raw_mode: Optional[str]) -> str:
    mode = (raw_mode or "direct").strip().lower()
    if mode not in {"direct", "guided"}:
        return "direct"
    return mode


def _normalize_learning_mode(raw_mode: Optional[str], default: str = "socratic") -> str:
    mode = (raw_mode or default).strip().lower()
    if mode not in {"socratic", "exploration"}:
        return default
    return mode


def _should_auto_advance_v2(structured_feedback: dict, mode: str, pass_streak: int) -> tuple[bool, str]:
    mastery_score = int(structured_feedback.get("mastery_score") or 0)
    confidence = float(structured_feedback.get("confidence") or 0.0)
    pass_stage = bool(structured_feedback.get("pass_stage"))
    misconception_count = len(
        [item for item in (structured_feedback.get("misconceptions") or []) if str(item).strip()]
    )

    normalized_mode = (mode or "balanced").strip().lower()
    if normalized_mode not in {"conservative", "balanced", "aggressive"}:
        normalized_mode = "balanced"

    if normalized_mode == "conservative":
        threshold_score = 85
        threshold_confidence = 0.8
        threshold_misconceptions = 0
        required_streak = 2
    elif normalized_mode == "aggressive":
        threshold_score = 65
        threshold_confidence = 0.6
        threshold_misconceptions = 2
        required_streak = 1
    else:
        threshold_score = 75
        threshold_confidence = 0.7
        threshold_misconceptions = 1
        required_streak = 2

    meets_now = (
        pass_stage
        and mastery_score >= threshold_score
        and confidence >= threshold_confidence
        and misconception_count <= threshold_misconceptions
    )
    qualifies = meets_now and (pass_streak + 1) >= required_streak
    reason = (
        f"V2 auto-advance: score={mastery_score}/{threshold_score}, "
        f"confidence={confidence:.2f}/{threshold_confidence:.2f}, "
        f"misconceptions={misconception_count}/{threshold_misconceptions}, "
        f"pass_streak={pass_streak + 1}/{required_streak}, pass_stage={pass_stage}"
    )
    return qualifies, reason


def _format_fallback_reason(reasons: List[str]) -> Optional[str]:
    cleaned = [item for item in reasons if item]
    if not cleaned:
        return None
    unique = list(dict.fromkeys(cleaned))
    return "; ".join(unique)


def _build_concept_evidence_snippet(user_text: str, anchor_text: str) -> str:
    source = "\n".join([str(user_text or "").strip(), str(anchor_text or "").strip()]).strip()
    if not source:
        return ""
    return source[:280]


def _estimate_concept_confidence(
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


async def _resolve_fallback_value(fallback):
    value = fallback() if callable(fallback) else fallback
    if asyncio.iscoroutine(value):
        return await value
    return value


async def _ensure_concept_record(
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
    concept = concept_result.scalar_one_or_none()
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
    if alias_result.scalar_one_or_none() is None:
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
            snippet=(snippet or "")[:500] or None,
            confidence=max(0.0, min(1.0, float(confidence or 0.0))),
        )
    )
    return concept


async def _ensure_concept_relation(
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


async def _register_problem_concept_candidates(
    db: AsyncSession,
    *,
    user_id: str,
    problem: Problem,
    learning_mode: str,
    source_turn_id: Optional[str],
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

    normalized_inputs = model_os_service.normalize_concepts(inferred_concepts, limit=max_candidates)
    if not normalized_inputs:
        return [], []

    existing_concepts = model_os_service.normalize_concepts(problem.associated_concepts or [], limit=max_concepts)
    existing_keys = {model_os_service.normalize_concept_key(item) for item in existing_concepts}

    existing_candidate_rows = await db.execute(
        select(ProblemConceptCandidate.normalized_text).where(
            ProblemConceptCandidate.problem_id == str(problem.id),
            ProblemConceptCandidate.user_id == user_id,
            ProblemConceptCandidate.status.in_(["pending", "accepted"]),
        )
    )
    existing_candidate_keys = {str(row[0] or "") for row in existing_candidate_rows.all()}

    accepted_concepts: List[str] = []
    pending_concepts: List[str] = []
    accepted_concept_ids: List[str] = []

    anchor_record = await _ensure_concept_record(
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
        if normalized in existing_keys or normalized in existing_candidate_keys:
            continue

        confidence = _estimate_concept_confidence(
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
                evidence_snippet=evidence_snippet[:500] or None,
            )
        )
        existing_candidate_keys.add(normalized)

        if status == "accepted":
            accepted_concepts.append(concept)
            concept_record = await _ensure_concept_record(
                db=db,
                user_id=user_id,
                concept_text=concept,
                source_type=source,
                source_id=str(problem.id),
                confidence=confidence,
                snippet=evidence_snippet,
            )
            if concept_record:
                accepted_concept_ids.append(concept_record.id)
        else:
            pending_concepts.append(concept)

    if accepted_concepts:
        merged = model_os_service.normalize_concepts(existing_concepts + accepted_concepts, limit=max_concepts)
        if merged != existing_concepts:
            problem.associated_concepts = merged
            model_os_service.refresh_problem_embedding(problem)

    if anchor_record and accepted_concept_ids:
        for target_id in accepted_concept_ids:
            await _ensure_concept_relation(
                db=db,
                user_id=user_id,
                source_concept_id=anchor_record.id,
                target_concept_id=target_id,
                relation_type="related",
            )

    return accepted_concepts, pending_concepts


async def _log_learning_event(
    db: AsyncSession,
    *,
    user_id: str,
    problem_id: Optional[str],
    event_type: str,
    learning_mode: Optional[str],
    trace_id: Optional[str],
    payload: dict,
) -> None:
    db.add(
        LearningEvent(
            user_id=user_id,
            problem_id=problem_id,
            event_type=event_type,
            learning_mode=learning_mode,
            trace_id=trace_id,
            payload_json=payload or {},
        )
    )


@router.post("/", response_model=ProblemResponse, status_code=201)
async def create_problem(
    problem_data: ProblemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    associated_concepts = await model_os_service.build_problem_concepts_resilient(
        problem_title=problem_data.title,
        problem_description=problem_data.description or "",
        seed_concepts=problem_data.associated_concepts,
        max_concepts=8,
    )

    db_problem = Problem(
        user_id=current_user.id,
        title=problem_data.title,
        description=problem_data.description,
        associated_concepts=associated_concepts,
        learning_mode=_normalize_learning_mode(problem_data.learning_mode, "socratic"),
        embedding=model_os_service.generate_embedding(
            model_os_service.build_problem_embedding_text(
                title=problem_data.title,
                description=problem_data.description,
                associated_concepts=associated_concepts,
            )
        ),
    )
    
    db.add(db_problem)
    await db.commit()
    await db.refresh(db_problem)
    
    existing_knowledge = []
    learning_path_data = await model_os_service.generate_learning_path_resilient(
        problem_title=problem_data.title,
        problem_description=problem_data.description or "",
        existing_knowledge=existing_knowledge,
        timeout_seconds=settings.LEARNING_PATH_TIMEOUT_SECONDS,
    )
    
    db_learning_path = LearningPath(
        problem_id=db_problem.id,
        path_data=learning_path_data,
        current_step=0,
    )
    
    db.add(db_learning_path)
    await db.commit()
    
    return db_problem


@router.get("/", response_model=List[ProblemResponse])
async def list_problems(
    q: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Problem)
        .where(Problem.user_id == current_user.id)
        .order_by(Problem.created_at.desc())
    )
    problems = result.scalars().all()
    if q:
        problems = list(problems)
        bind = db.get_bind()
        fallback_ranked = model_os_service.rank_problems(problems, q)
        if bind and bind.dialect.name == "postgresql" and problems:
            query_embedding = model_os_service.generate_embedding(q)
            embedding_param = model_os_service.serialize_embedding_for_pgvector(query_embedding)
            native_result = await db.execute(
                text(
                    """
                    SELECT p.id
                    FROM problems p
                    WHERE p.user_id = :user_id
                      AND p.embedding IS NOT NULL
                    ORDER BY p.embedding <=> CAST(:embedding AS vector)
                    LIMIT :limit
                    """
                ),
                {
                    "user_id": str(current_user.id),
                    "embedding": embedding_param,
                    "limit": max(len(problems), 1),
                },
            )
            problem_map = {str(problem.id): problem for problem in problems}
            native_ranked = [
                problem_map[row[0]]
                for row in native_result.all()
                if row[0] in problem_map
            ]
            seen = set()
            merged = []
            for problem in native_ranked + fallback_ranked:
                pid = str(problem.id)
                if pid in seen:
                    continue
                seen.add(pid)
                merged.append(problem)
            problems = merged
        else:
            problems = fallback_ranked
    return problems


@router.get("/{problem_id}", response_model=ProblemResponse)
async def get_problem(
    problem_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id)
        )
    )
    problem = result.scalar_one_or_none()
    
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    
    return problem


@router.put("/{problem_id}", response_model=ProblemResponse)
async def update_problem(
    problem_id: UUID,
    problem_data: ProblemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id)
        )
    )
    problem = result.scalar_one_or_none()
    
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    
    if problem_data.title:
        problem.title = problem_data.title
    if problem_data.description:
        problem.description = problem_data.description
    if problem_data.associated_concepts:
        problem.associated_concepts = problem_data.associated_concepts
    if problem_data.learning_mode:
        problem.learning_mode = _normalize_learning_mode(problem_data.learning_mode, problem.learning_mode or "socratic")
    if problem_data.status:
        problem.status = problem_data.status
    model_os_service.refresh_problem_embedding(problem)
    
    await db.commit()
    await db.refresh(problem)
    
    return problem


@router.delete("/{problem_id}", status_code=204)
async def delete_problem(
    problem_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id)
        )
    )
    problem = result.scalar_one_or_none()
    
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    
    await db.delete(problem)
    await db.commit()
    
    return None


@router.post("/{problem_id}/responses", response_model=ProblemResponseResponse)
async def create_response(
    problem_id: UUID,
    response_data: ProblemResponseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id),
        )
    )
    problem = result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    learning_mode = _normalize_learning_mode(response_data.learning_mode, problem.learning_mode or "socratic")
    if learning_mode != "socratic":
        raise HTTPException(status_code=400, detail="The /responses route only supports socratic mode")
    problem.learning_mode = learning_mode

    learning_path_result = await db.execute(
        select(LearningPath).where(LearningPath.problem_id == str(problem_id))
    )
    learning_path = learning_path_result.scalar_one_or_none()
    current_step_index, current_step_data = _resolve_current_step(learning_path)

    step_concept = (current_step_data or {}).get("concept") or problem.title
    step_description = (current_step_data or {}).get("description") or ""
    step_resources = (current_step_data or {}).get("resources") or []
    model_examples = model_os_service.normalize_concepts(
        [step_concept, *(problem.associated_concepts or []), *step_resources],
        limit=10,
    )

    trace_id = str(uuid.uuid4())
    started_at = time.monotonic()
    llm_calls = 0
    llm_latency_ms = 0
    fallback_reasons: List[str] = []
    max_llm_calls = max(1, int(settings.PROBLEM_MAX_LLM_CALLS_PER_REQUEST))
    response_timeout = max(4, int(settings.PROBLEM_RESPONSE_TIMEOUT_SECONDS))

    async def guarded_llm_call(label: str, call_factory, fallback, low_priority: bool = False):
        nonlocal llm_calls, llm_latency_ms
        elapsed = time.monotonic() - started_at
        remaining = response_timeout - elapsed
        if remaining <= 0:
            fallback_reasons.append(f"timeout_budget:{label}")
            return await _resolve_fallback_value(fallback)
        if low_priority and remaining <= 2:
            fallback_reasons.append(f"skip_low_priority:{label}")
            return await _resolve_fallback_value(fallback)
        if llm_calls >= max_llm_calls:
            fallback_reasons.append(f"budget_exceeded:{label}")
            return await _resolve_fallback_value(fallback)

        llm_calls += 1
        llm_started = time.monotonic()
        try:
            return await asyncio.wait_for(call_factory(), timeout=max(1, int(remaining)))
        except asyncio.TimeoutError:
            fallback_reasons.append(f"timeout:{label}")
            return await _resolve_fallback_value(fallback)
        except Exception:
            fallback_reasons.append(f"error:{label}")
            return await _resolve_fallback_value(fallback)
        finally:
            llm_latency_ms += int((time.monotonic() - llm_started) * 1000)

    retrieval_context = await model_os_service.build_retrieval_context(
        db=db,
        user_id=str(current_user.id),
        query=(
            f"{problem.title}\n"
            f"Step {current_step_index + 1}: {step_concept}\n"
            f"{step_description}\n"
            f"{response_data.user_response}"
        ),
        source="problem_response",
    )

    structured_feedback = await guarded_llm_call(
        label="structured_feedback",
        call_factory=lambda: model_os_service.generate_feedback_structured(
            user_response=response_data.user_response,
            concept=step_concept,
            model_examples=model_examples,
            retrieval_context=retrieval_context,
        ),
        fallback=lambda: model_os_service.normalize_feedback_structured(
            {
                "correctness": "partially correct",
                "misconceptions": [],
                "suggestions": ["Please clarify your key assumptions with one concrete example."],
                "next_question": f"What boundary case can falsify your current view of '{step_concept}'?",
            }
        ),
    )
    structured_feedback = model_os_service.normalize_feedback_structured(structured_feedback)

    misconceptions = [
        str(item).strip()
        for item in (structured_feedback.get("misconceptions") or [])
        if str(item).strip()
    ]
    suggestions = [
        str(item).strip()
        for item in (structured_feedback.get("suggestions") or [])
        if str(item).strip()
    ]
    next_question = str(structured_feedback.get("next_question") or "").strip()

    concept_context_parts = [
        f"User response:\n{response_data.user_response}",
        f"Current step concept:\n{step_concept}",
        f"Current step description:\n{step_description}",
    ]
    if misconceptions:
        concept_context_parts.append(
            "Misconceptions:\n" + "\n".join(f"- {item}" for item in misconceptions)
        )
    if suggestions:
        concept_context_parts.append(
            "Suggestions:\n" + "\n".join(f"- {item}" for item in suggestions)
        )
    if next_question:
        concept_context_parts.append(f"Next question:\n{next_question}")

    max_concepts = max(6, int(settings.PROBLEM_MAX_ASSOCIATED_CONCEPTS))
    inferred_concepts = await guarded_llm_call(
        label="concept_extraction",
        call_factory=lambda: model_os_service.extract_related_concepts_resilient(
            problem_title=problem.title,
            problem_description="\n\n".join(concept_context_parts),
            limit=min(max_concepts, 10),
        ),
        fallback=lambda: [step_concept],
        low_priority=True,
    )
    inferred_concepts = model_os_service.normalize_concepts(inferred_concepts or [], limit=10)

    mode_metadata = {
        "turn_source": "response",
        "step_index": current_step_index,
        "step_concept": step_concept,
        "step_description": step_description,
    }
    db_turn = ProblemTurn(
        user_id=str(current_user.id),
        problem_id=str(problem_id),
        learning_mode=learning_mode,
        step_index=current_step_index,
        user_text=response_data.user_response,
        assistant_text=None,
        mode_metadata=mode_metadata,
    )
    db.add(db_turn)
    await db.flush()

    evidence_snippet = _build_concept_evidence_snippet(response_data.user_response, step_concept)
    accepted_concepts, pending_concepts = await _register_problem_concept_candidates(
        db=db,
        user_id=str(current_user.id),
        problem=problem,
        learning_mode=learning_mode,
        source_turn_id=str(db_turn.id),
        inferred_concepts=inferred_concepts + [step_concept],
        source="response",
        anchor_concept=step_concept,
        user_text=response_data.user_response,
        retrieval_context=retrieval_context,
        evidence_snippet=evidence_snippet,
    )

    auto_advanced = False
    new_current_step = learning_path.current_step if learning_path else None
    v2_decision_reason = ""
    pass_streak = 0

    if learning_path:
        if settings.PROBLEM_AUTO_ADVANCE_V2_ENABLED:
            streak_rows = await db.execute(
                select(ProblemMasteryEvent.pass_stage)
                .where(
                    ProblemMasteryEvent.problem_id == str(problem_id),
                    ProblemMasteryEvent.step_index == current_step_index,
                    ProblemMasteryEvent.user_id == str(current_user.id),
                )
                .order_by(ProblemMasteryEvent.created_at.desc())
                .limit(8)
            )
            for row in streak_rows.all():
                if bool(row[0]):
                    pass_streak += 1
                else:
                    break
            should_advance, v2_decision_reason = _should_auto_advance_v2(
                structured_feedback=structured_feedback,
                mode=settings.PROBLEM_AUTO_ADVANCE_MODE,
                pass_streak=pass_streak,
            )
        else:
            should_advance = _should_auto_advance(
                structured_feedback,
                settings.PROBLEM_AUTO_ADVANCE_MODE,
            )
            v2_decision_reason = (
                f"V1 auto-advance mode={settings.PROBLEM_AUTO_ADVANCE_MODE}, verdict={structured_feedback.get('correctness', '')}"
            )

        if should_advance:
            total_steps = len(learning_path.path_data or [])
            if total_steps > 0 and int(learning_path.current_step or 0) < total_steps:
                learning_path.current_step = min(total_steps, int(learning_path.current_step or 0) + 1)
                new_current_step = learning_path.current_step
                auto_advanced = True

                if learning_path.current_step >= total_steps:
                    problem.status = "completed"
                elif learning_path.current_step > 0:
                    problem.status = "in-progress"
                else:
                    problem.status = "new"

    if v2_decision_reason:
        structured_feedback["decision_reason"] = (
            f"{structured_feedback.get('decision_reason', '')} | {v2_decision_reason}".strip(" |")
        )

    mode_metadata = {
        **mode_metadata,
        "accepted_concepts": accepted_concepts,
        "pending_concepts": pending_concepts,
        "auto_advanced": auto_advanced,
        "new_current_step": new_current_step,
    }
    formatted_feedback = model_os_service.format_feedback_text(structured_feedback)
    db_turn.assistant_text = formatted_feedback
    db_turn.mode_metadata = mode_metadata

    db_response = ProblemResponseModel(
        problem_id=str(problem_id),
        user_response=response_data.user_response,
        system_feedback=formatted_feedback,
        learning_mode=learning_mode,
        mode_metadata=mode_metadata,
    )
    db.add(db_response)
    await db.flush()

    mastery_event = ProblemMasteryEvent(
        user_id=str(current_user.id),
        problem_id=str(problem_id),
        step_index=current_step_index,
        mastery_score=int(structured_feedback.get("mastery_score") or 0),
        confidence=float(structured_feedback.get("confidence") or 0.0),
        pass_stage=bool(structured_feedback.get("pass_stage")),
        auto_advanced=auto_advanced,
        correctness_label=str(structured_feedback.get("correctness") or ""),
        decision_reason=str(structured_feedback.get("decision_reason") or ""),
    )
    db.add(mastery_event)

    await _log_learning_event(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem_id),
        event_type="problem_response_evaluated",
        learning_mode=learning_mode,
        trace_id=trace_id,
        payload={
            "step_index": current_step_index,
            "mastery_score": structured_feedback.get("mastery_score"),
            "confidence": structured_feedback.get("confidence"),
            "auto_advanced": auto_advanced,
            "accepted_concepts": accepted_concepts,
            "pending_concepts": pending_concepts,
            "llm_calls": llm_calls,
            "llm_latency_ms": llm_latency_ms,
            "fallback_reason": _format_fallback_reason(fallback_reasons),
        },
    )

    await db.commit()
    await db.refresh(db_response)

    return {
        "id": db_response.id,
        "problem_id": db_response.problem_id,
        "turn_id": db_turn.id,
        "learning_mode": learning_mode,
        "mode_metadata": mode_metadata,
        "user_response": db_response.user_response,
        "system_feedback": db_response.system_feedback,
        "structured_feedback": structured_feedback,
        "auto_advanced": auto_advanced,
        "new_current_step": new_current_step,
        "new_concepts": accepted_concepts,
        "accepted_concepts": accepted_concepts,
        "pending_concepts": pending_concepts,
        "concepts_updated": bool(accepted_concepts),
        "trace_id": trace_id,
        "llm_calls": llm_calls,
        "llm_latency_ms": llm_latency_ms,
        "fallback_reason": _format_fallback_reason(fallback_reasons),
        "created_at": db_response.created_at,
    }


@router.get("/{problem_id}/responses", response_model=List[ProblemResponseResponse])
async def list_responses(
    problem_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id)
        )
    )
    if not problem_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Problem not found")

    result = await db.execute(
        select(ProblemResponseModel)
        .where(ProblemResponseModel.problem_id == str(problem_id))
        .order_by(ProblemResponseModel.created_at.asc())
    )
    responses = []
    for response in result.scalars().all():
        responses.append({
            "id": response.id,
            "problem_id": response.problem_id,
            "turn_id": None,
            "learning_mode": _normalize_learning_mode(getattr(response, "learning_mode", None), "socratic"),
            "mode_metadata": getattr(response, "mode_metadata", None) or {},
            "user_response": response.user_response,
            "system_feedback": response.system_feedback,
            "structured_feedback": model_os_service.parse_feedback_text(response.system_feedback),
            "created_at": response.created_at,
        })
    return responses


@router.get("/{problem_id}/turns", response_model=List[ProblemTurnResponse])
async def list_problem_turns(
    problem_id: UUID,
    learning_mode: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id),
        )
    )
    if not problem_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Problem not found")

    query = (
        select(ProblemTurn)
        .where(
            ProblemTurn.problem_id == str(problem_id),
            ProblemTurn.user_id == str(current_user.id),
        )
        .order_by(ProblemTurn.created_at.desc())
    )
    if learning_mode:
        query = query.where(
            ProblemTurn.learning_mode == _normalize_learning_mode(learning_mode, "socratic")
        )

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{problem_id}/concept-candidates", response_model=List[ProblemConceptCandidateResponse])
async def list_problem_concept_candidates(
    problem_id: UUID,
    status: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id),
        )
    )
    if not problem_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Problem not found")

    query = (
        select(ProblemConceptCandidate)
        .where(
            ProblemConceptCandidate.problem_id == str(problem_id),
            ProblemConceptCandidate.user_id == str(current_user.id),
        )
        .order_by(ProblemConceptCandidate.created_at.desc())
    )
    if status:
        query = query.where(ProblemConceptCandidate.status == status.strip().lower())

    result = await db.execute(query)
    return list(result.scalars().all())


@router.post(
    "/{problem_id}/concept-candidates/{candidate_id}/accept",
    response_model=ProblemConceptCandidateActionResponse,
)
async def accept_problem_concept_candidate(
    problem_id: UUID,
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trace_id = str(uuid.uuid4())
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id),
        )
    )
    problem = problem_result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    candidate_result = await db.execute(
        select(ProblemConceptCandidate).where(
            ProblemConceptCandidate.id == str(candidate_id),
            ProblemConceptCandidate.problem_id == str(problem_id),
            ProblemConceptCandidate.user_id == str(current_user.id),
        )
    )
    candidate = candidate_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Concept candidate not found")

    candidate.status = "accepted"
    candidate.reviewer_id = str(current_user.id)
    candidate.reviewed_at = datetime.utcnow()

    existing = model_os_service.normalize_concepts(
        problem.associated_concepts or [],
        limit=max(6, int(settings.PROBLEM_MAX_ASSOCIATED_CONCEPTS)),
    )
    merged = model_os_service.normalize_concepts(
        existing + [candidate.concept_text],
        limit=max(6, int(settings.PROBLEM_MAX_ASSOCIATED_CONCEPTS)),
    )
    accepted_concepts: List[str] = []
    if merged != existing:
        problem.associated_concepts = merged
        model_os_service.refresh_problem_embedding(problem)
        accepted_concepts = [candidate.concept_text]

    anchor_concept = (
        model_os_service.normalize_concepts(problem.associated_concepts or [], limit=1) or [problem.title]
    )[0]
    target_concept = await _ensure_concept_record(
        db=db,
        user_id=str(current_user.id),
        concept_text=candidate.concept_text,
        source_type="candidate_accept",
        source_id=str(problem.id),
        confidence=float(candidate.confidence or 0.0),
        snippet=candidate.evidence_snippet,
    )
    anchor_record = await _ensure_concept_record(
        db=db,
        user_id=str(current_user.id),
        concept_text=anchor_concept,
        source_type="candidate_accept",
        source_id=str(problem.id),
        confidence=0.9,
        snippet=candidate.evidence_snippet,
    )
    if anchor_record and target_concept:
        await _ensure_concept_relation(
            db=db,
            user_id=str(current_user.id),
            source_concept_id=anchor_record.id,
            target_concept_id=target_concept.id,
            relation_type="related",
        )

    await _log_learning_event(
        db=db,
        user_id=str(current_user.id),
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

    await db.commit()
    await db.refresh(candidate)
    return {
        "candidate": candidate,
        "accepted_concepts": accepted_concepts,
        "trace_id": trace_id,
    }


@router.post(
    "/{problem_id}/concept-candidates/{candidate_id}/reject",
    response_model=ProblemConceptCandidateActionResponse,
)
async def reject_problem_concept_candidate(
    problem_id: UUID,
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trace_id = str(uuid.uuid4())
    candidate_result = await db.execute(
        select(ProblemConceptCandidate).where(
            ProblemConceptCandidate.id == str(candidate_id),
            ProblemConceptCandidate.problem_id == str(problem_id),
            ProblemConceptCandidate.user_id == str(current_user.id),
        )
    )
    candidate = candidate_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Concept candidate not found")

    candidate.status = "rejected"
    candidate.reviewer_id = str(current_user.id)
    candidate.reviewed_at = datetime.utcnow()

    await _log_learning_event(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem_id),
        event_type="concept_candidate_rejected",
        learning_mode=candidate.learning_mode,
        trace_id=trace_id,
        payload={
            "candidate_id": str(candidate.id),
            "concept_text": candidate.concept_text,
            "confidence": candidate.confidence,
        },
    )

    await db.commit()
    await db.refresh(candidate)
    return {
        "candidate": candidate,
        "accepted_concepts": [],
        "trace_id": trace_id,
    }


@router.post("/{problem_id}/concepts/rollback", response_model=ProblemConceptRollbackResponse)
async def rollback_problem_concept(
    problem_id: UUID,
    payload: ProblemConceptRollbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trace_id = str(uuid.uuid4())
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id),
        )
    )
    problem = problem_result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    normalized_target = model_os_service.normalize_concept_key(payload.concept_text)
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
            "reviewer_id": str(current_user.id),
            "reviewed_at": datetime.utcnow(),
            "problem_id": str(problem.id),
            "user_id": str(current_user.id),
            "normalized_text": normalized_target,
        },
    )

    await _log_learning_event(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem.id),
        event_type="concept_rolled_back",
        learning_mode=problem.learning_mode,
        trace_id=trace_id,
        payload={
            "concept_text": payload.concept_text,
            "removed": removed,
            "reason": payload.reason or "",
        },
    )

    await db.commit()
    return {
        "removed": removed,
        "concept_text": payload.concept_text,
        "associated_concepts": kept if removed else existing,
        "trace_id": trace_id,
    }


@router.get("/{problem_id}/learning-path/hint", response_model=LearningStepHintResponse)
async def get_learning_step_hint(
    problem_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id)
        )
    )
    problem = problem_result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    path_result = await db.execute(
        select(LearningPath).where(LearningPath.problem_id == str(problem_id))
    )
    learning_path = path_result.scalar_one_or_none()
    if not learning_path:
        raise HTTPException(status_code=404, detail="Learning path not found")

    step_index, step_data = _resolve_current_step(learning_path)
    step_concept = (step_data or {}).get("concept") or problem.title
    step_description = (step_data or {}).get("description") or (problem.description or "")

    latest_feedback = None
    latest_feedback_result = await db.execute(
        select(ProblemResponseModel.system_feedback)
        .where(ProblemResponseModel.problem_id == str(problem_id))
        .order_by(desc(ProblemResponseModel.created_at))
        .limit(1)
    )
    latest_feedback_row = latest_feedback_result.first()
    if latest_feedback_row and latest_feedback_row[0]:
        latest_feedback = model_os_service.parse_feedback_text(latest_feedback_row[0])

    recent_result = await db.execute(
        select(ProblemResponseModel.user_response)
        .where(ProblemResponseModel.problem_id == str(problem_id))
        .order_by(desc(ProblemResponseModel.created_at))
        .limit(3)
    )
    recent_rows = recent_result.all()
    recent_responses = [row[0] for row in reversed(recent_rows) if row and row[0]]

    structured_hint = await model_os_service.generate_step_hint(
        problem_title=problem.title,
        problem_description=problem.description or "",
        step_concept=step_concept,
        step_description=step_description,
        recent_responses=recent_responses,
        latest_feedback=latest_feedback,
    )
    hint = model_os_service.format_step_hint_text(structured_hint)

    return {
        "step_index": step_index,
        "step_concept": step_concept,
        "hint": hint,
        "structured_hint": structured_hint,
    }


@router.post("/{problem_id}/ask", response_model=LearningQuestionResponse)
async def ask_learning_question(
    problem_id: UUID,
    payload: LearningQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id)
        )
    )
    problem = problem_result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    learning_mode = _normalize_learning_mode(payload.learning_mode, problem.learning_mode or "exploration")
    if learning_mode != "exploration":
        raise HTTPException(status_code=400, detail="The /ask route only supports exploration mode")
    problem.learning_mode = learning_mode

    path_result = await db.execute(
        select(LearningPath).where(LearningPath.problem_id == str(problem_id))
    )
    learning_path = path_result.scalar_one_or_none()
    step_index, step_data = _resolve_current_step(learning_path)
    step_concept = (step_data or {}).get("concept") or problem.title
    step_description = (step_data or {}).get("description") or (problem.description or "")
    mode = _normalize_answer_mode(payload.answer_mode)
    trace_id = str(uuid.uuid4())
    started_at = time.monotonic()
    llm_calls = 0
    llm_latency_ms = 0
    fallback_reasons: List[str] = []
    max_llm_calls = max(1, int(settings.PROBLEM_MAX_LLM_CALLS_PER_REQUEST))
    response_timeout = max(4, int(settings.PROBLEM_RESPONSE_TIMEOUT_SECONDS))

    async def guarded_llm_call(label: str, call_factory, fallback, low_priority: bool = False):
        nonlocal llm_calls, llm_latency_ms
        elapsed = time.monotonic() - started_at
        remaining = response_timeout - elapsed
        if remaining <= 0:
            fallback_reasons.append(f"timeout_budget:{label}")
            return await _resolve_fallback_value(fallback)
        if low_priority and remaining <= 2:
            fallback_reasons.append(f"skip_low_priority:{label}")
            return await _resolve_fallback_value(fallback)
        if llm_calls >= max_llm_calls:
            fallback_reasons.append(f"budget_exceeded:{label}")
            return await _resolve_fallback_value(fallback)

        llm_calls += 1
        llm_started = time.monotonic()
        try:
            return await asyncio.wait_for(call_factory(), timeout=max(1, int(remaining)))
        except asyncio.TimeoutError:
            fallback_reasons.append(f"timeout:{label}")
            return await _resolve_fallback_value(fallback)
        except Exception:
            fallback_reasons.append(f"error:{label}")
            return await _resolve_fallback_value(fallback)
        finally:
            llm_latency_ms += int((time.monotonic() - llm_started) * 1000)

    retrieval_context = await model_os_service.build_retrieval_context(
        db=db,
        user_id=str(current_user.id),
        query=(
            f"{problem.title}\n"
            f"Current step: {step_concept}\n"
            f"Question: {payload.question}"
        ),
        source="problem_inline_qa",
    )

    if mode == "direct":
        style_instruction = (
            "Answer directly and accurately. Keep structure: "
            "1) concise definition, 2) key distinction, 3) one concrete example, "
            "4) one common pitfall."
        )
    else:
        style_instruction = (
            "Use guided style. First give a short hint, then one mini-example, "
            "and end with one focused check question."
        )

    prompt = f"""The learner asked a question during a step-by-step learning flow.

Problem: {problem.title}
Problem description: {problem.description or "N/A"}
Current step concept: {step_concept}
Current step description: {step_description}

Learner question: {payload.question}

{style_instruction}
"""

    answer = await guarded_llm_call(
        label="ask_answer",
        call_factory=lambda: model_os_service.generate_with_context(
            prompt=prompt,
            context=[{"role": "user", "content": payload.question}],
            retrieval_context=retrieval_context,
        ),
        fallback=lambda: model_os_service.build_learning_answer_fallback(
            question=payload.question,
            step_concept=step_concept,
            mode=mode,
        ),
    )

    ask_concepts = await guarded_llm_call(
        label="ask_concept_extraction",
        call_factory=lambda: model_os_service.extract_related_concepts_resilient(
            problem_title=problem.title,
            problem_description=(
                f"Question: {payload.question}\n"
                f"Answer: {answer}\n"
                f"Current step concept: {step_concept}\n"
                f"Current step description: {step_description}"
            ),
            limit=max(3, int(settings.PROBLEM_CONCEPT_MAX_CANDIDATES_PER_TURN)),
        ),
        fallback=lambda: [step_concept],
        low_priority=True,
    )

    mode_metadata = {
        "turn_source": "ask",
        "step_index": step_index,
        "step_concept": step_concept,
        "step_description": step_description,
        "answer_mode": mode,
    }
    db_turn = ProblemTurn(
        user_id=str(current_user.id),
        problem_id=str(problem.id),
        learning_mode=learning_mode,
        step_index=step_index,
        user_text=payload.question,
        assistant_text=answer,
        mode_metadata=mode_metadata,
    )
    db.add(db_turn)
    await db.flush()

    evidence_snippet = _build_concept_evidence_snippet(payload.question, answer)
    accepted_concepts, pending_concepts = await _register_problem_concept_candidates(
        db=db,
        user_id=str(current_user.id),
        problem=problem,
        learning_mode=learning_mode,
        source_turn_id=str(db_turn.id),
        inferred_concepts=ask_concepts + [step_concept],
        source="ask",
        anchor_concept=step_concept,
        user_text=f"{payload.question}\n{answer}",
        retrieval_context=retrieval_context,
        evidence_snippet=evidence_snippet,
    )
    suggested_next_focus = f"Use your question to refine one boundary of '{step_concept}'."
    mode_metadata = {
        **mode_metadata,
        "accepted_concepts": accepted_concepts,
        "pending_concepts": pending_concepts,
        "suggested_next_focus": suggested_next_focus,
    }
    db_turn.mode_metadata = mode_metadata

    await _log_learning_event(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem.id),
        event_type="problem_inline_qa",
        learning_mode=learning_mode,
        trace_id=trace_id,
        payload={
            "step_index": step_index,
            "answer_mode": mode,
            "accepted_concepts": accepted_concepts,
            "pending_concepts": pending_concepts,
            "llm_calls": llm_calls,
            "llm_latency_ms": llm_latency_ms,
            "fallback_reason": _format_fallback_reason(fallback_reasons),
        },
    )
    await db.commit()

    return {
        "turn_id": db_turn.id,
        "learning_mode": learning_mode,
        "mode_metadata": mode_metadata,
        "question": payload.question,
        "answer": answer,
        "answer_mode": mode,
        "step_index": step_index,
        "step_concept": step_concept,
        "suggested_next_focus": suggested_next_focus,
        "accepted_concepts": accepted_concepts,
        "pending_concepts": pending_concepts,
        "trace_id": trace_id,
        "llm_calls": llm_calls,
        "llm_latency_ms": llm_latency_ms,
        "fallback_reason": _format_fallback_reason(fallback_reasons),
    }


@router.get("/{problem_id}/learning-path", response_model=LearningPathResponse)
async def get_learning_path(
    problem_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # First verify the problem belongs to the current user
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id)
        )
    )
    problem = problem_result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    result = await db.execute(
        select(LearningPath).where(
            LearningPath.problem_id == str(problem_id),
        )
    )
    learning_path = result.scalar_one_or_none()

    if not learning_path:
        raise HTTPException(status_code=404, detail="Learning path not found")

    return learning_path


@router.put("/{problem_id}/learning-path", response_model=LearningPathResponse)
async def update_learning_path_progress(
    problem_id: UUID,
    data: LearningPathProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id)
        )
    )
    problem = problem_result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    result = await db.execute(
        select(LearningPath).where(LearningPath.problem_id == str(problem_id))
    )
    learning_path = result.scalar_one_or_none()
    if not learning_path:
        raise HTTPException(status_code=404, detail="Learning path not found")

    total_steps = len(learning_path.path_data) if learning_path.path_data else 0
    if data.current_step < 0 or data.current_step > total_steps:
        raise HTTPException(status_code=400, detail="Invalid step number")

    learning_path.current_step = data.current_step

    if total_steps > 0:
        if data.current_step >= total_steps:
            problem.status = "completed"
        elif data.current_step > 0:
            problem.status = "in-progress"
        else:
            problem.status = "new"

    await db.commit()
    await db.refresh(learning_path)
    return learning_path
