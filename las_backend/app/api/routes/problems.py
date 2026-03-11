import asyncio
import json
import re
import time
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, desc
from sqlalchemy.orm import selectinload
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
    ProblemConceptCandidate,
    ProblemPathCandidate,
    LearningEvent,
)
from app.schemas.problem import (
    ProblemCreate,
    ProblemUpdate,
    ProblemResponse,
    ProblemResponseCreate,
    ProblemResponseResponse,
    SocraticQuestionResponse,
    LearningStepHintResponse,
    LearningQuestionRequest,
    LearningQuestionResponse,
    ProblemTurnResponse,
    ProblemConceptCandidateResponse,
    ProblemConceptCandidateActionResponse,
    ProblemConceptCandidateHandoffResponse,
    ProblemConceptCandidateMergeRequest,
    ProblemPathCandidateResponse,
    ProblemPathCandidateDecisionRequest,
    ProblemPathCandidateDecisionResponse,
    ProblemConceptRollbackRequest,
    ProblemConceptRollbackResponse,
)
from app.api.routes.auth import get_current_user
from app.api.routes.problem_exploration_support import (
    _build_exploration_next_actions,
    _build_exploration_path_suggestions,
    _derive_question_concepts,
    _filter_grounded_ask_concepts,
    _infer_exploration_answer_type,
    _normalize_exploration_answer_type,
    _select_answered_concepts,
    _select_related_concepts,
)
from app.api.routes.problem_concept_candidate_handoff_support import (
    ensure_candidate_review_schedule,
    ensure_model_card_for_candidate,
    load_candidate_review_schedule,
    serialize_problem_concept_candidate_handoff,
)
from app.api.routes.problem_concept_registration_support import (
    build_concept_evidence_snippet as _build_concept_evidence_snippet,
    ensure_concept_record as _ensure_concept_record,
    ensure_concept_relation as _ensure_concept_relation,
    register_problem_concept_candidates as _register_problem_concept_candidates,
)
from app.api.routes.problem_concept_candidate_moderation_support import (
    ProblemConceptCandidateModerationDeps,
    accept_problem_concept_candidate as accept_problem_concept_candidate_support,
    load_owned_problem_concept_candidate,
    merge_problem_concept_candidate as merge_problem_concept_candidate_support,
    postpone_problem_concept_candidate as postpone_problem_concept_candidate_support,
    refresh_problem_concept_candidate,
    reject_problem_concept_candidate as reject_problem_concept_candidate_support,
    rollback_problem_concept as rollback_problem_concept_support,
)
from app.api.routes.problem_learning_path_support import (
    _default_path_insertion,
    _load_active_learning_path,
    _resolve_current_step,
)
from app.api.routes.problem_learning_path_routes import router as problem_learning_path_router
from app.api.routes.problem_persistence_guard_support import run_optional_persist
from app.api.routes.problem_path_candidate_support import (
    build_socratic_path_candidate_specs,
    decide_problem_path_candidate_action,
    register_problem_path_candidates,
    serialize_problem_path_candidate,
)
from app.api.routes.problem_socratic_support import (
    build_socratic_question_response_payload,
    build_socratic_question_stream_response,
)
from app.api.routes.problem_socratic_response_support import (
    SocraticResponseSupportDeps,
    _should_auto_advance,
    _should_auto_advance_v2,
    build_socratic_response_stream,
    complete_socratic_response,
)
from app.services.model_os_service import model_os_service

router = APIRouter(prefix="/problems", tags=["Problems"])
settings = get_settings()
router.include_router(problem_learning_path_router)


def _problem_create_concept_timeout_seconds() -> float:
    return float(max(2, min(int(settings.LLM_REQUEST_TIMEOUT_SECONDS), 4)))


def _problem_create_path_timeout_seconds() -> float:
    return float(max(4, min(int(settings.LEARNING_PATH_TIMEOUT_SECONDS), 7)))


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


def _normalize_problem_list_sort(raw_sort: Optional[str]) -> str:
    sort = str(raw_sort or "updated_desc").strip().lower()
    if sort not in {"updated_desc", "created_desc", "created_asc"}:
        return "updated_desc"
    return sort


def _problem_sort_clauses(sort: str):
    if sort == "created_asc":
        return [Problem.created_at.asc(), Problem.updated_at.asc()]
    if sort == "created_desc":
        return [Problem.created_at.desc(), Problem.updated_at.desc()]
    return [Problem.updated_at.desc(), Problem.created_at.desc()]


async def _list_turn_concept_candidates(
    db: AsyncSession,
    *,
    user_id: str,
    problem_id: str,
    source_turn_id: str,
) -> List[dict]:
    result = await db.execute(
        select(ProblemConceptCandidate)
        .where(
            ProblemConceptCandidate.user_id == user_id,
            ProblemConceptCandidate.problem_id == problem_id,
            ProblemConceptCandidate.source_turn_id == source_turn_id,
        )
        .order_by(desc(ProblemConceptCandidate.confidence), desc(ProblemConceptCandidate.created_at))
    )
    return [
        {
            "name": row.concept_text,
            "confidence": round(float(row.confidence or 0.0), 4),
            "status": row.status,
        }
        for row in result.scalars().all()
    ]


def _format_fallback_reason(reasons: List[str]) -> Optional[str]:
    cleaned = [item for item in reasons if item]
    if not cleaned:
        return None
    unique = list(dict.fromkeys(cleaned))
    return "; ".join(unique)


async def _resolve_fallback_value(fallback):
    value = fallback() if callable(fallback) else fallback
    if asyncio.iscoroutine(value):
        return await value
    return value


def _exploration_concept_candidate_limit() -> int:
    configured_limit = int(settings.PROBLEM_CONCEPT_MAX_CANDIDATES_PER_TURN)
    return max(1, min(3, configured_limit))


async def _complete_exploration_learning_turn(
    *,
    db: AsyncSession,
    current_user: User,
    problem: Problem,
    payload: LearningQuestionRequest,
    learning_path: Optional[LearningPath],
    learning_mode: str,
    mode: str,
    step_index: int,
    step_concept: str,
    step_description: str,
    answer: str,
    retrieval_context: Optional[str],
    trace_id: str,
    llm_metrics: dict,
    fallback_reasons: List[str],
    guarded_llm_call,
):
    mode_metadata = {
        "turn_source": "ask",
        "step_index": step_index,
        "step_concept": step_concept,
        "step_description": step_description,
        "answer_mode": mode,
    }
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
            limit=_exploration_concept_candidate_limit(),
        ),
        fallback=lambda: [step_concept],
        low_priority=True,
    )
    ask_concepts = model_os_service.filter_low_signal_concepts(
        ask_concepts,
        limit=_exploration_concept_candidate_limit(),
    )

    db_turn = ProblemTurn(
        user_id=str(current_user.id),
        problem_id=str(problem.id),
        path_id=str(learning_path.id) if learning_path else None,
        learning_mode=learning_mode,
        step_index=step_index,
        user_text=payload.question,
        assistant_text=answer,
        mode_metadata=mode_metadata,
    )
    db.add(db_turn)
    await db.flush()

    evidence_snippet = _build_concept_evidence_snippet(payload.question, answer)
    answer_type = _normalize_exploration_answer_type(_infer_exploration_answer_type(payload.question))
    question_concepts = _derive_question_concepts(
        question=payload.question,
        answer_type=answer_type,
        candidate_concepts=[*(problem.associated_concepts or []), *ask_concepts, step_concept],
    )
    question_concepts = model_os_service.filter_low_signal_concepts(question_concepts, limit=2)
    filtered_ask_concepts = _filter_grounded_ask_concepts(
        question=payload.question,
        answer=answer,
        ask_concepts=ask_concepts,
        question_concepts=question_concepts,
        step_concept=step_concept,
    )
    filtered_ask_concepts = model_os_service.filter_low_signal_concepts(
        filtered_ask_concepts,
        limit=_exploration_concept_candidate_limit(),
    )
    # Candidate artifacts should prefer concepts grounded in the answer itself,
    # then backfill with question targets when there is remaining budget.
    candidate_concepts = model_os_service.normalize_concepts(
        [*filtered_ask_concepts, *question_concepts],
        limit=_exploration_concept_candidate_limit(),
    ) or [step_concept]
    accepted_concepts, pending_concepts = await run_optional_persist(
        db=db,
        fallback_reasons=fallback_reasons,
        label="concept_candidate_persist",
        operation=lambda: _register_problem_concept_candidates(
            db=db,
            user_id=str(current_user.id),
            problem=problem,
            learning_mode=learning_mode,
            source_turn_id=str(db_turn.id),
            source_path_id=str(learning_path.id) if learning_path else None,
            inferred_concepts=candidate_concepts,
            source="ask",
            anchor_concept=step_concept,
            user_text=f"{payload.question}\n{answer}",
            retrieval_context=retrieval_context,
            evidence_snippet=evidence_snippet,
        ),
        default=([], []),
    )
    await db.flush()
    concept_pool = model_os_service.normalize_concepts(
        [*question_concepts, *filtered_ask_concepts, *accepted_concepts, *pending_concepts],
        limit=8,
    )
    answered_concepts = _select_answered_concepts(
        question=payload.question,
        step_concept=step_concept,
        inferred_concepts=concept_pool,
        answer_type=answer_type,
        question_concepts=question_concepts,
    )
    related_concepts = _select_related_concepts(
        answered_concepts=answered_concepts,
        step_concept=step_concept,
        inferred_concepts=concept_pool,
    )
    derived_candidates = await _list_turn_concept_candidates(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem.id),
        source_turn_id=str(db_turn.id),
    )
    next_learning_actions = _build_exploration_next_actions(
        answer_type=answer_type,
        question=payload.question,
        step_concept=step_concept,
        answered_concepts=answered_concepts,
        related_concepts=related_concepts,
    )
    path_suggestions = _build_exploration_path_suggestions(
        answer_type=answer_type,
        question=payload.question,
        step_concept=step_concept,
        answered_concepts=answered_concepts,
        related_concepts=related_concepts,
    )
    derived_path_candidates = await run_optional_persist(
        db=db,
        fallback_reasons=fallback_reasons,
        label="path_candidate_persist",
        operation=lambda: register_problem_path_candidates(
            db=db,
            user_id=str(current_user.id),
            problem_id=str(problem.id),
            learning_mode=learning_mode,
            source_turn_id=str(db_turn.id),
            step_index=step_index,
            candidate_specs=[
                {
                    "type": suggestion.get("type"),
                    "title": suggestion.get("title"),
                    "reason": suggestion.get("reason"),
                    "recommended_insertion": _default_path_insertion(str(suggestion.get("type") or "")),
                }
                for suggestion in path_suggestions
            ],
            evidence_snippet=payload.question,
        ),
        default=[],
    )
    return_to_main_path_hint = not bool(path_suggestions)
    suggested_next_focus = next_learning_actions[0] if next_learning_actions else f"Use your question to refine one boundary of '{step_concept}'."
    mode_metadata = {
        **mode_metadata,
        "answer_type": answer_type,
        "answered_concepts": answered_concepts,
        "related_concepts": related_concepts,
        "derived_candidates": derived_candidates,
        "derived_path_candidates": derived_path_candidates,
        "next_learning_actions": next_learning_actions,
        "path_suggestions": path_suggestions,
        "return_to_main_path_hint": return_to_main_path_hint,
        "accepted_concepts": accepted_concepts,
        "pending_concepts": pending_concepts,
        "suggested_next_focus": suggested_next_focus,
    }
    db_turn.mode_metadata = mode_metadata

    await run_optional_persist(
        db=db,
        fallback_reasons=fallback_reasons,
        label="learning_event_persist",
        operation=lambda: _log_learning_event(
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
                "llm_calls": llm_metrics["llm_calls"],
                "llm_latency_ms": llm_metrics["llm_latency_ms"],
                "fallback_reason": _format_fallback_reason(fallback_reasons),
            },
        ),
        default=None,
    )
    fallback_reason = _format_fallback_reason(fallback_reasons)
    await db.commit()

    return {
        "turn_id": db_turn.id,
        "learning_mode": learning_mode,
        "mode_metadata": mode_metadata,
        "question": payload.question,
        "answer": answer,
        "answer_mode": mode,
        "answer_type": answer_type,
        "answered_concepts": answered_concepts,
        "related_concepts": related_concepts,
        "derived_candidates": derived_candidates,
        "derived_path_candidates": derived_path_candidates,
        "next_learning_actions": next_learning_actions,
        "path_suggestions": path_suggestions,
        "return_to_main_path_hint": return_to_main_path_hint,
        "step_index": step_index,
        "step_concept": step_concept,
        "suggested_next_focus": suggested_next_focus,
        "accepted_concepts": accepted_concepts,
        "pending_concepts": pending_concepts,
        "trace_id": trace_id,
        "llm_calls": llm_metrics["llm_calls"],
        "llm_latency_ms": llm_metrics["llm_latency_ms"],
        "fallback_reason": fallback_reason,
    }

def _normalize_concept_candidate_status(status: Optional[str]) -> str:
    normalized = str(status or "pending").strip().lower()
    if normalized not in {"pending", "accepted", "rejected", "reverted", "postponed", "merged"}:
        return "pending"
    return normalized


def _build_turn_preview(turn: Optional[ProblemTurn]) -> Optional[str]:
    if not turn:
        return None
    raw = str(turn.user_text or turn.assistant_text or "").strip()
    if not raw:
        return None
    compact = re.sub(r"\s+", " ", raw)
    return compact[:180] + ("..." if len(compact) > 180 else "")


def _serialize_problem_concept_candidate(candidate: ProblemConceptCandidate) -> dict:
    turn = getattr(candidate, "source_turn", None)
    return {
        "id": candidate.id,
        "problem_id": candidate.problem_id,
        "concept_text": candidate.concept_text,
        "source": candidate.source,
        "learning_mode": _normalize_learning_mode(candidate.learning_mode, "socratic"),
        "source_turn_id": candidate.source_turn_id,
        "confidence": round(float(candidate.confidence or 0.0), 4),
        "status": _normalize_concept_candidate_status(candidate.status),
        "merged_into_concept": candidate.merged_into_concept,
        "linked_model_card_id": candidate.linked_model_card_id,
        "evidence_snippet": candidate.evidence_snippet,
        "source_turn_preview": _build_turn_preview(turn),
        "source_turn_created_at": turn.created_at.isoformat() if turn and turn.created_at else None,
        "reviewed_at": candidate.reviewed_at.isoformat() if candidate.reviewed_at else None,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
    }

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


def _build_socratic_response_support_deps() -> SocraticResponseSupportDeps:
    return SocraticResponseSupportDeps(
        build_concept_evidence_snippet=_build_concept_evidence_snippet,
        build_socratic_path_candidate_specs=build_socratic_path_candidate_specs,
        format_fallback_reason=_format_fallback_reason,
        log_learning_event=_log_learning_event,
        register_problem_concept_candidates=_register_problem_concept_candidates,
        register_problem_path_candidates=register_problem_path_candidates,
        resolve_fallback_value=_resolve_fallback_value,
    )


def _build_concept_candidate_moderation_deps() -> ProblemConceptCandidateModerationDeps:
    return ProblemConceptCandidateModerationDeps(
        ensure_concept_record=_ensure_concept_record,
        ensure_concept_relation=_ensure_concept_relation,
        log_learning_event=_log_learning_event,
    )


@router.post("/", response_model=ProblemResponse, status_code=201)
async def create_problem(
    problem_data: ProblemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    max_concepts = 8
    seed_concepts = model_os_service.normalize_concepts(problem_data.associated_concepts or [], limit=max_concepts)
    fallback_concepts = model_os_service.build_problem_concepts_local(
        problem_title=problem_data.title,
        problem_description=problem_data.description or "",
        seed_concepts=problem_data.associated_concepts,
        max_concepts=max_concepts,
    )
    try:
        associated_concepts = await asyncio.wait_for(
            model_os_service.build_problem_concepts_resilient(
                problem_title=problem_data.title,
                problem_description=problem_data.description or "",
                seed_concepts=problem_data.associated_concepts,
                max_concepts=max_concepts,
            ),
            timeout=_problem_create_concept_timeout_seconds(),
        )
    except asyncio.TimeoutError:
        associated_concepts = fallback_concepts
    except Exception:
        associated_concepts = fallback_concepts
    associated_concepts = model_os_service.normalize_concepts(associated_concepts or fallback_concepts, limit=max_concepts)
    if not associated_concepts:
        associated_concepts = ["Core concept"]

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
    path_timeout = _problem_create_path_timeout_seconds()
    try:
        learning_path_data = await asyncio.wait_for(
            model_os_service.generate_learning_path_resilient(
                problem_title=problem_data.title,
                problem_description=problem_data.description or "",
                existing_knowledge=existing_knowledge,
                associated_concepts=associated_concepts,
                timeout_seconds=path_timeout,
            ),
            timeout=max(path_timeout + 1, 5),
        )
    except asyncio.TimeoutError:
        learning_path_data = model_os_service._build_fallback_learning_path(
            problem_title=problem_data.title,
            problem_description=problem_data.description or "",
            existing_knowledge=existing_knowledge,
            associated_concepts=associated_concepts,
        )
    except Exception:
        learning_path_data = model_os_service._build_fallback_learning_path(
            problem_title=problem_data.title,
            problem_description=problem_data.description or "",
            existing_knowledge=existing_knowledge,
            associated_concepts=associated_concepts,
        )
    if not learning_path_data:
        learning_path_data = model_os_service._build_fallback_learning_path(
            problem_title=problem_data.title,
            problem_description=problem_data.description or "",
            existing_knowledge=existing_knowledge,
            associated_concepts=associated_concepts,
        )
    
    db_learning_path = LearningPath(
        problem_id=db_problem.id,
        title=problem_data.title,
        kind="main",
        is_active=True,
        path_data=learning_path_data,
        current_step=0,
    )
    
    db.add(db_learning_path)
    await db.commit()
    
    return db_problem


@router.get("/", response_model=List[ProblemResponse])
async def list_problems(
    q: Optional[str] = Query(default=None),
    learning_mode: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    sort: str = Query(default="updated_desc"),
    limit: int = Query(default=12, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    normalized_mode = learning_mode if learning_mode in {"socratic", "exploration"} else None
    normalized_status = str(status or "").strip() or None
    normalized_sort = _normalize_problem_list_sort(sort)

    query = select(Problem).where(Problem.user_id == current_user.id)
    if normalized_mode:
        query = query.where(Problem.learning_mode == normalized_mode)
    if normalized_status:
        query = query.where(Problem.status == normalized_status)

    if q:
        result = await db.execute(query.order_by(*_problem_sort_clauses(normalized_sort)))
        problems = list(result.scalars().all())
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
        return list(problems)[offset:offset + limit]

    result = await db.execute(
        query
        .order_by(*_problem_sort_clauses(normalized_sort))
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


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


@router.get("/{problem_id}/socratic-question", response_model=SocraticQuestionResponse)
async def get_socratic_question(
    problem_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id),
        )
    )
    problem = problem_result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return await build_socratic_question_response_payload(
        db=db,
        problem=problem,
        user_id=str(current_user.id),
    )


@router.get("/{problem_id}/socratic-question/stream")
async def stream_socratic_question(
    problem_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    problem_result = await db.execute(
        select(Problem).where(
            Problem.id == str(problem_id),
            Problem.user_id == str(current_user.id),
        )
    )
    problem = problem_result.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return await build_socratic_question_stream_response(
        db=db,
        problem=problem,
        user_id=str(current_user.id),
    )


@router.post("/{problem_id}/responses/stream")
async def stream_response(
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
    return await build_socratic_response_stream(
        deps=_build_socratic_response_support_deps(),
        problem_id=problem_id,
        response_data=response_data,
        current_user=current_user,
        db=db,
        problem=problem,
    )


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

    return await complete_socratic_response(
        deps=_build_socratic_response_support_deps(),
        problem_id=problem_id,
        response_data=response_data,
        current_user=current_user,
        db=db,
        problem=problem,
    )


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
            "question_kind": (getattr(response, "mode_metadata", None) or {}).get("question_kind"),
            "socratic_question": (getattr(response, "mode_metadata", None) or {}).get("socratic_question"),
            "evaluation": (getattr(response, "mode_metadata", None) or {}).get("evaluation"),
            "decision": (getattr(response, "mode_metadata", None) or {}).get("decision"),
            "follow_up": (getattr(response, "mode_metadata", None) or {}).get("follow_up"),
            "user_response": response.user_response,
            "system_feedback": response.system_feedback,
            "structured_feedback": model_os_service.parse_feedback_text(response.system_feedback),
            "derived_path_candidates": (getattr(response, "mode_metadata", None) or {}).get("derived_path_candidates") or [],
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


@router.get("/{problem_id}/path-candidates", response_model=List[ProblemPathCandidateResponse])
async def list_problem_path_candidates(
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
        select(ProblemPathCandidate)
        .where(
            ProblemPathCandidate.problem_id == str(problem_id),
            ProblemPathCandidate.user_id == str(current_user.id),
        )
        .order_by(ProblemPathCandidate.created_at.desc())
    )
    if status:
        query = query.where(ProblemPathCandidate.status == status.strip().lower())

    result = await db.execute(query)
    return [serialize_problem_path_candidate(item) for item in result.scalars().all()]


@router.post(
    "/{problem_id}/path-candidates/{candidate_id}/decide",
    response_model=ProblemPathCandidateDecisionResponse,
)
async def decide_problem_path_candidate(
    problem_id: UUID,
    candidate_id: UUID,
    payload: ProblemPathCandidateDecisionRequest,
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
        select(ProblemPathCandidate).where(
            ProblemPathCandidate.id == str(candidate_id),
            ProblemPathCandidate.problem_id == str(problem_id),
            ProblemPathCandidate.user_id == str(current_user.id),
        )
    )
    candidate = candidate_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Path candidate not found")

    action = str(payload.action or "").strip().lower()
    decision_result = await decide_problem_path_candidate_action(
        db=db,
        problem=problem,
        candidate=candidate,
        action=action,
    )

    await _log_learning_event(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem_id),
        event_type="path_candidate_decided",
        learning_mode=candidate.learning_mode,
        trace_id=trace_id,
        payload={
            "candidate_id": str(candidate.id),
            "path_type": candidate.path_type,
            "title": candidate.title,
            "action": action,
            "selected_insertion": candidate.selected_insertion,
            "applied_path_id": decision_result.applied_path_id,
        },
    )

    await db.commit()
    await db.refresh(candidate)
    return {
        "candidate": serialize_problem_path_candidate(candidate),
        "trace_id": trace_id,
    }


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
        .options(selectinload(ProblemConceptCandidate.source_turn))
        .where(
            ProblemConceptCandidate.problem_id == str(problem_id),
            ProblemConceptCandidate.user_id == str(current_user.id),
        )
        .order_by(ProblemConceptCandidate.created_at.desc())
    )
    if status:
        query = query.where(ProblemConceptCandidate.status == _normalize_concept_candidate_status(status))

    result = await db.execute(query)
    return [_serialize_problem_concept_candidate(row) for row in result.scalars().all()]


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

    candidate = await load_owned_problem_concept_candidate(
        db=db,
        problem_id=str(problem_id),
        candidate_id=str(candidate_id),
        user_id=str(current_user.id),
    )
    accepted_concepts = await accept_problem_concept_candidate_support(
        db=db,
        deps=_build_concept_candidate_moderation_deps(),
        problem=problem,
        candidate=candidate,
        user_id=str(current_user.id),
        trace_id=trace_id,
    )

    await db.commit()
    refreshed_candidate = await refresh_problem_concept_candidate(
        db=db,
        candidate_id=str(candidate.id),
    )
    return {
        "candidate": _serialize_problem_concept_candidate(refreshed_candidate),
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
    candidate = await load_owned_problem_concept_candidate(
        db=db,
        problem_id=str(problem_id),
        candidate_id=str(candidate_id),
        user_id=str(current_user.id),
    )
    await reject_problem_concept_candidate_support(
        db=db,
        deps=_build_concept_candidate_moderation_deps(),
        candidate=candidate,
        problem_id=str(problem_id),
        user_id=str(current_user.id),
        trace_id=trace_id,
    )

    await db.commit()
    refreshed_candidate = await refresh_problem_concept_candidate(
        db=db,
        candidate_id=str(candidate.id),
    )
    return {
        "candidate": _serialize_problem_concept_candidate(refreshed_candidate),
        "accepted_concepts": [],
        "trace_id": trace_id,
    }


@router.post(
    "/{problem_id}/concept-candidates/{candidate_id}/merge",
    response_model=ProblemConceptCandidateActionResponse,
)
async def merge_problem_concept_candidate(
    problem_id: UUID,
    candidate_id: UUID,
    payload: ProblemConceptCandidateMergeRequest,
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

    candidate = await load_owned_problem_concept_candidate(
        db=db,
        problem_id=str(problem_id),
        candidate_id=str(candidate_id),
        user_id=str(current_user.id),
    )
    await merge_problem_concept_candidate_support(
        db=db,
        deps=_build_concept_candidate_moderation_deps(),
        problem=problem,
        candidate=candidate,
        user_id=str(current_user.id),
        target_concept_text=payload.target_concept_text,
        trace_id=trace_id,
    )

    await db.commit()
    refreshed_candidate = await refresh_problem_concept_candidate(
        db=db,
        candidate_id=str(candidate.id),
    )
    return {
        "candidate": _serialize_problem_concept_candidate(refreshed_candidate),
        "accepted_concepts": [],
        "trace_id": trace_id,
    }


@router.post(
    "/{problem_id}/concept-candidates/{candidate_id}/postpone",
    response_model=ProblemConceptCandidateActionResponse,
)
async def postpone_problem_concept_candidate(
    problem_id: UUID,
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trace_id = str(uuid.uuid4())
    candidate = await load_owned_problem_concept_candidate(
        db=db,
        problem_id=str(problem_id),
        candidate_id=str(candidate_id),
        user_id=str(current_user.id),
    )
    await postpone_problem_concept_candidate_support(
        db=db,
        deps=_build_concept_candidate_moderation_deps(),
        candidate=candidate,
        problem_id=str(problem_id),
        user_id=str(current_user.id),
        trace_id=trace_id,
    )

    await db.commit()
    refreshed_candidate = await refresh_problem_concept_candidate(
        db=db,
        candidate_id=str(candidate.id),
    )
    return {
        "candidate": _serialize_problem_concept_candidate(refreshed_candidate),
        "accepted_concepts": [],
        "trace_id": trace_id,
    }


@router.post(
    "/{problem_id}/concept-candidates/{candidate_id}/promote",
    response_model=ProblemConceptCandidateHandoffResponse,
)
async def promote_problem_concept_candidate_to_model_card(
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
        select(ProblemConceptCandidate)
        .options(selectinload(ProblemConceptCandidate.source_turn))
        .where(
            ProblemConceptCandidate.id == str(candidate_id),
            ProblemConceptCandidate.problem_id == str(problem_id),
            ProblemConceptCandidate.user_id == str(current_user.id),
        )
    )
    candidate = candidate_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Concept candidate not found")
    if candidate.status not in {"accepted", "merged"}:
        raise HTTPException(status_code=400, detail="Only accepted or merged concepts can be promoted")

    model_card, created_model_card = await ensure_model_card_for_candidate(
        db=db,
        user_id=str(current_user.id),
        problem=problem,
        candidate=candidate,
        build_turn_preview=_build_turn_preview,
        normalize_learning_mode=_normalize_learning_mode,
    )
    review_schedule = await load_candidate_review_schedule(
        db=db,
        user_id=str(current_user.id),
        model_card_id=str(model_card.id),
    )

    await _log_learning_event(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem.id),
        event_type="concept_candidate_promoted_to_model_card",
        learning_mode=candidate.learning_mode,
        trace_id=trace_id,
        payload={
            "candidate_id": str(candidate.id),
            "concept_text": candidate.concept_text,
            "model_card_id": str(model_card.id),
            "created_model_card": created_model_card,
        },
    )

    await db.commit()
    return serialize_problem_concept_candidate_handoff(
        candidate_payload=_serialize_problem_concept_candidate(candidate),
        model_card=model_card,
        created_model_card=created_model_card,
        review_schedule=review_schedule,
        trace_id=trace_id,
    )


@router.post(
    "/{problem_id}/concept-candidates/{candidate_id}/schedule-review",
    response_model=ProblemConceptCandidateHandoffResponse,
)
async def schedule_problem_concept_candidate_review(
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
        select(ProblemConceptCandidate)
        .options(selectinload(ProblemConceptCandidate.source_turn))
        .where(
            ProblemConceptCandidate.id == str(candidate_id),
            ProblemConceptCandidate.problem_id == str(problem_id),
            ProblemConceptCandidate.user_id == str(current_user.id),
        )
    )
    candidate = candidate_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Concept candidate not found")
    if candidate.status not in {"accepted", "merged"}:
        raise HTTPException(status_code=400, detail="Only accepted or merged concepts can enter review")

    model_card, created_model_card = await ensure_model_card_for_candidate(
        db=db,
        user_id=str(current_user.id),
        problem=problem,
        candidate=candidate,
        build_turn_preview=_build_turn_preview,
        normalize_learning_mode=_normalize_learning_mode,
    )
    review_schedule = await load_candidate_review_schedule(
        db=db,
        user_id=str(current_user.id),
        model_card_id=str(model_card.id),
    )
    if review_schedule is None:
        review_schedule = await ensure_candidate_review_schedule(
            db=db,
            user_id=str(current_user.id),
            model_card_id=str(model_card.id),
        )

    await _log_learning_event(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem.id),
        event_type="concept_candidate_review_scheduled",
        learning_mode=candidate.learning_mode,
        trace_id=trace_id,
        payload={
            "candidate_id": str(candidate.id),
            "concept_text": candidate.concept_text,
            "model_card_id": str(model_card.id),
            "created_model_card": created_model_card,
            "schedule_id": str(review_schedule.id),
        },
    )

    await db.commit()
    return serialize_problem_concept_candidate_handoff(
        candidate_payload=_serialize_problem_concept_candidate(candidate),
        model_card=model_card,
        created_model_card=created_model_card,
        review_schedule=review_schedule,
        trace_id=trace_id,
    )


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

    response_payload = await rollback_problem_concept_support(
        db=db,
        deps=_build_concept_candidate_moderation_deps(),
        problem=problem,
        user_id=str(current_user.id),
        concept_text=payload.concept_text,
        reason=payload.reason,
        trace_id=trace_id,
    )

    await db.commit()
    return response_payload


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

    learning_path = await _load_active_learning_path(db, problem_id=str(problem_id))
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

    learning_path = await _load_active_learning_path(db, problem_id=str(problem_id))
    step_index, step_data = _resolve_current_step(learning_path)
    step_concept = (step_data or {}).get("concept") or problem.title
    step_description = (step_data or {}).get("description") or (problem.description or "")
    mode = _normalize_answer_mode(payload.answer_mode)
    trace_id = str(uuid.uuid4())
    started_at = time.monotonic()
    llm_metrics = {
        "llm_calls": 0,
        "llm_latency_ms": 0,
    }
    fallback_reasons: List[str] = []
    max_llm_calls = max(1, int(settings.PROBLEM_MAX_LLM_CALLS_PER_REQUEST))
    response_timeout = max(4, int(settings.PROBLEM_RESPONSE_TIMEOUT_SECONDS))

    async def guarded_llm_call(label: str, call_factory, fallback, low_priority: bool = False):
        elapsed = time.monotonic() - started_at
        remaining = response_timeout - elapsed
        if remaining <= 0:
            fallback_reasons.append(f"timeout_budget:{label}")
            return await _resolve_fallback_value(fallback)
        if low_priority and remaining <= 2:
            fallback_reasons.append(f"skip_low_priority:{label}")
            return await _resolve_fallback_value(fallback)
        if llm_metrics["llm_calls"] >= max_llm_calls:
            fallback_reasons.append(f"budget_exceeded:{label}")
            return await _resolve_fallback_value(fallback)

        llm_metrics["llm_calls"] += 1
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
            llm_metrics["llm_latency_ms"] += int((time.monotonic() - llm_started) * 1000)

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
    return await _complete_exploration_learning_turn(
        db=db,
        current_user=current_user,
        problem=problem,
        payload=payload,
        learning_path=learning_path,
        learning_mode=learning_mode,
        mode=mode,
        step_index=step_index,
        step_concept=step_concept,
        step_description=step_description,
        answer=answer,
        retrieval_context=retrieval_context,
        trace_id=trace_id,
        llm_metrics=llm_metrics,
        fallback_reasons=fallback_reasons,
        guarded_llm_call=guarded_llm_call,
    )


@router.post("/{problem_id}/ask/stream")
async def stream_learning_question(
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

    learning_path = await _load_active_learning_path(db, problem_id=str(problem_id))
    step_index, step_data = _resolve_current_step(learning_path)
    step_concept = (step_data or {}).get("concept") or problem.title
    step_description = (step_data or {}).get("description") or (problem.description or "")
    mode = _normalize_answer_mode(payload.answer_mode)
    trace_id = str(uuid.uuid4())
    started_at = time.monotonic()
    llm_metrics = {
        "llm_calls": 0,
        "llm_latency_ms": 0,
    }
    fallback_reasons: List[str] = []
    max_llm_calls = max(1, int(settings.PROBLEM_MAX_LLM_CALLS_PER_REQUEST))
    response_timeout = max(4, int(settings.PROBLEM_RESPONSE_TIMEOUT_SECONDS))

    async def guarded_llm_call(label: str, call_factory, fallback, low_priority: bool = False):
        elapsed = time.monotonic() - started_at
        remaining = response_timeout - elapsed
        if remaining <= 0:
            fallback_reasons.append(f"timeout_budget:{label}")
            return await _resolve_fallback_value(fallback)
        if low_priority and remaining <= 2:
            fallback_reasons.append(f"skip_low_priority:{label}")
            return await _resolve_fallback_value(fallback)
        if llm_metrics["llm_calls"] >= max_llm_calls:
            fallback_reasons.append(f"budget_exceeded:{label}")
            return await _resolve_fallback_value(fallback)

        llm_metrics["llm_calls"] += 1
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
            llm_metrics["llm_latency_ms"] += int((time.monotonic() - llm_started) * 1000)

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

    async def event_generator():
        answer_chunks: List[str] = []
        answer = ""
        if llm_metrics["llm_calls"] >= max_llm_calls:
            fallback_reasons.append("budget_exceeded:ask_answer")
        else:
            llm_metrics["llm_calls"] += 1
            llm_started = time.monotonic()
            try:
                async for token in model_os_service.stream_generate_with_context(
                    prompt=prompt,
                    context=[{"role": "user", "content": payload.question}],
                    retrieval_context=retrieval_context,
                ):
                    if not answer_chunks and token.startswith("Error:"):
                        raise RuntimeError(token)
                    answer_chunks.append(token)
                    yield {"event": "token", "data": token}
            except Exception:
                fallback_reasons.append("error:ask_answer")
            finally:
                llm_metrics["llm_latency_ms"] += int((time.monotonic() - llm_started) * 1000)

        if answer_chunks:
            answer = "".join(answer_chunks).strip()

        if not answer:
            if not any(reason.startswith(("error:ask_answer", "budget_exceeded:ask_answer")) for reason in fallback_reasons):
                fallback_reasons.append("timeout_budget:ask_answer")
            answer = await _resolve_fallback_value(
                lambda: model_os_service.build_learning_answer_fallback(
                    question=payload.question,
                    step_concept=step_concept,
                    mode=mode,
                )
            )
            if answer:
                yield {"event": "token", "data": answer}

        try:
            response = await _complete_exploration_learning_turn(
                db=db,
                current_user=current_user,
                problem=problem,
                payload=payload,
                learning_path=learning_path,
                learning_mode=learning_mode,
                mode=mode,
                step_index=step_index,
                step_concept=step_concept,
                step_description=step_description,
                answer=answer,
                retrieval_context=retrieval_context,
                trace_id=trace_id,
                llm_metrics=llm_metrics,
                fallback_reasons=fallback_reasons,
                guarded_llm_call=guarded_llm_call,
            )
            yield {"event": "final", "data": json.dumps(jsonable_encoder(response))}
            yield {"event": "done", "data": ""}
        except Exception:
            await db.rollback()
            yield {
                "event": "error",
                "data": json.dumps({"message": "Failed to complete streamed learning answer."}),
            }

    return EventSourceResponse(event_generator())
