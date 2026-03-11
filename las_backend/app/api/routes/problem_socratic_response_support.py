import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional
from uuid import UUID

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.problem_learning_path_support import (
    _load_active_learning_path,
    _resolve_current_step,
)
from app.api.routes.problem_socratic_support import _resolve_socratic_question_payload
from app.core.config import get_settings
from app.models.entities.user import (
    Problem,
    ProblemMasteryEvent,
    ProblemResponse as ProblemResponseModel,
    ProblemTurn,
    User,
)
from app.schemas.problem import (
    ProblemResponseCreate,
    TurnDecisionResponse,
    TurnEvaluationResponse,
    TurnFollowUpResponse,
)
from app.services.model_os_service import model_os_service

settings = get_settings()


def _normalize_learning_mode(raw_mode: Optional[str], default: str = "socratic") -> str:
    mode = (raw_mode or default).strip().lower()
    if mode not in {"socratic", "exploration"}:
        return default
    return mode


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

    normalized_mode = (mode or "balanced").strip().lower()
    if normalized_mode not in {"conservative", "balanced", "aggressive"}:
        normalized_mode = "balanced"

    if normalized_mode == "conservative":
        return has_full and len([item for item in (structured_feedback or {}).get("misconceptions") or [] if str(item).strip()]) == 0
    if normalized_mode == "aggressive":
        return has_full or has_partial

    misconception_count = len([item for item in (structured_feedback or {}).get("misconceptions") or [] if str(item).strip()])
    if has_full:
        return misconception_count <= 1
    if has_partial:
        return misconception_count == 0
    return False


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


def _build_turn_evaluation(structured_feedback: dict) -> TurnEvaluationResponse:
    return TurnEvaluationResponse(
        mastery_score=int(structured_feedback.get("mastery_score") or 0),
        dimension_scores=dict(structured_feedback.get("dimension_scores") or {}),
        confidence=float(structured_feedback.get("confidence") or 0.0),
        correctness=str(structured_feedback.get("correctness") or ""),
    )


def _build_turn_decision(*, advance: bool, progression_ran: bool, reason: str) -> TurnDecisionResponse:
    return TurnDecisionResponse(
        advance=advance,
        progression_ran=progression_ran,
        reason=str(reason or "").strip(),
    )


@dataclass(frozen=True)
class SocraticResponseSupportDeps:
    build_concept_evidence_snippet: Callable[[str, str], str]
    build_socratic_path_candidate_specs: Callable[..., List[dict]]
    format_fallback_reason: Callable[[List[str]], Optional[str]]
    log_learning_event: Callable[..., Awaitable[None]]
    register_problem_concept_candidates: Callable[..., Awaitable[tuple[List[str], List[str]]]]
    register_problem_path_candidates: Callable[..., Awaitable[List[dict]]]
    resolve_fallback_value: Callable[[Any], Awaitable[Any]]


async def complete_socratic_response(
    *,
    deps: SocraticResponseSupportDeps,
    problem_id: UUID,
    response_data: ProblemResponseCreate,
    current_user: User,
    db: AsyncSession,
    problem: Problem,
    on_progress: Optional[Callable[[str, dict], Awaitable[None]]] = None,
):
    learning_mode = _normalize_learning_mode(response_data.learning_mode, problem.learning_mode or "socratic")
    if learning_mode != "socratic":
        raise HTTPException(status_code=400, detail="The /responses route only supports socratic mode")
    problem.learning_mode = learning_mode

    async def emit_progress(event: str, payload: Optional[dict] = None):
        if on_progress:
            await on_progress(event, payload or {})

    learning_path = await _load_active_learning_path(db, problem_id=str(problem_id))
    current_step_index, current_step_data = _resolve_current_step(learning_path)

    step_concept = (current_step_data or {}).get("concept") or problem.title
    step_description = (current_step_data or {}).get("description") or ""
    step_resources = (current_step_data or {}).get("resources") or []
    model_examples = model_os_service.normalize_concepts(
        [step_concept, *(problem.associated_concepts or []), *step_resources],
        limit=10,
    )
    question_kind, socratic_question, _, _, _, socratic_question_fallback, _, _ = (
        await _resolve_socratic_question_payload(
            db=db,
            problem=problem,
            user_id=str(current_user.id),
            step_index=current_step_index,
            step_concept=step_concept,
            step_description=step_description,
            provided_question_kind=response_data.question_kind,
            provided_question=response_data.socratic_question,
            use_llm=False,
        )
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
            return await deps.resolve_fallback_value(fallback)
        if low_priority and remaining <= 2:
            fallback_reasons.append(f"skip_low_priority:{label}")
            return await deps.resolve_fallback_value(fallback)
        if llm_calls >= max_llm_calls:
            fallback_reasons.append(f"budget_exceeded:{label}")
            return await deps.resolve_fallback_value(fallback)

        llm_calls += 1
        llm_started = time.monotonic()
        try:
            return await asyncio.wait_for(call_factory(), timeout=max(1, int(remaining)))
        except asyncio.TimeoutError:
            fallback_reasons.append(f"timeout:{label}")
            return await deps.resolve_fallback_value(fallback)
        except Exception:
            fallback_reasons.append(f"error:{label}")
            return await deps.resolve_fallback_value(fallback)
        finally:
            llm_latency_ms += int((time.monotonic() - llm_started) * 1000)

    await emit_progress("status", {"phase": "evaluating_feedback"})
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
    await emit_progress(
        "preview",
        {
            "phase": "feedback_ready",
            "correctness": str(structured_feedback.get("correctness") or ""),
            "mastery_score": int(structured_feedback.get("mastery_score") or 0),
            "confidence": float(structured_feedback.get("confidence") or 0.0),
            "question_kind": question_kind,
        },
    )

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
    await emit_progress("status", {"phase": "extracting_artifacts"})
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
        "question_kind": question_kind,
        "socratic_question": socratic_question,
    }
    db_turn = ProblemTurn(
        user_id=str(current_user.id),
        problem_id=str(problem_id),
        path_id=str(learning_path.id) if learning_path else None,
        learning_mode=learning_mode,
        step_index=current_step_index,
        user_text=response_data.user_response,
        assistant_text=None,
        mode_metadata=mode_metadata,
    )
    db.add(db_turn)
    await db.flush()

    evidence_snippet = deps.build_concept_evidence_snippet(response_data.user_response, step_concept)
    accepted_concepts, pending_concepts = await deps.register_problem_concept_candidates(
        db=db,
        user_id=str(current_user.id),
        problem=problem,
        learning_mode=learning_mode,
        source_turn_id=str(db_turn.id),
        source_path_id=str(learning_path.id) if learning_path else None,
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

    if learning_path and question_kind == "checkpoint":
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
    elif question_kind == "probe":
        v2_decision_reason = "Probe questions collect clarification and do not run progression logic."

    if v2_decision_reason:
        structured_feedback["decision_reason"] = (
            f"{structured_feedback.get('decision_reason', '')} | {v2_decision_reason}".strip(" |")
        )

    evaluation = _build_turn_evaluation(structured_feedback)
    decision = _build_turn_decision(
        advance=auto_advanced,
        progression_ran=(question_kind == "checkpoint"),
        reason=str(structured_feedback.get("decision_reason") or ""),
    )
    if question_kind == "probe":
        next_question_kind = "checkpoint" if evaluation.mastery_score >= 70 else "probe"
        follow_up_needed = True
    else:
        next_question_kind = "probe" if structured_feedback.get("misconceptions") else "checkpoint"
        follow_up_needed = not auto_advanced
    follow_up_question = None
    if follow_up_needed:
        follow_up_question = str(structured_feedback.get("next_question") or "").strip() or model_os_service.build_socratic_question_fallback(
            step_concept=step_concept,
            question_kind=next_question_kind,
            latest_feedback=structured_feedback,
        )
    follow_up = TurnFollowUpResponse(
        needed=follow_up_needed,
        question=follow_up_question,
        question_kind=next_question_kind if follow_up_needed else None,
    )

    await emit_progress("status", {"phase": "saving_turn"})
    derived_path_candidates = await deps.register_problem_path_candidates(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem_id),
        learning_mode=learning_mode,
        source_turn_id=str(db_turn.id),
        step_index=current_step_index,
        candidate_specs=deps.build_socratic_path_candidate_specs(
            step_concept=step_concept,
            question_kind=question_kind,
            structured_feedback=structured_feedback,
            auto_advanced=auto_advanced,
        ),
        evidence_snippet=response_data.user_response,
    )

    mode_metadata = {
        **mode_metadata,
        "evaluation": evaluation.model_dump(),
        "decision": decision.model_dump(),
        "follow_up": follow_up.model_dump(),
        "derived_path_candidates": derived_path_candidates,
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

    await deps.log_learning_event(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem_id),
        event_type="problem_response_evaluated",
        learning_mode=learning_mode,
        trace_id=trace_id,
        payload={
            "step_index": current_step_index,
            "question_kind": question_kind,
            "mastery_score": structured_feedback.get("mastery_score"),
            "confidence": structured_feedback.get("confidence"),
            "auto_advanced": auto_advanced,
            "progression_ran": question_kind == "checkpoint",
            "accepted_concepts": accepted_concepts,
            "pending_concepts": pending_concepts,
            "llm_calls": llm_calls,
            "llm_latency_ms": llm_latency_ms,
            "fallback_reason": deps.format_fallback_reason(fallback_reasons),
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
        "question_kind": question_kind,
        "socratic_question": socratic_question,
        "evaluation": evaluation,
        "decision": decision,
        "follow_up": follow_up,
        "user_response": db_response.user_response,
        "system_feedback": db_response.system_feedback,
        "structured_feedback": structured_feedback,
        "auto_advanced": auto_advanced,
        "new_current_step": new_current_step,
        "new_concepts": accepted_concepts,
        "accepted_concepts": accepted_concepts,
        "pending_concepts": pending_concepts,
        "derived_path_candidates": derived_path_candidates,
        "concepts_updated": bool(accepted_concepts),
        "trace_id": trace_id,
        "llm_calls": llm_calls,
        "llm_latency_ms": llm_latency_ms,
        "fallback_reason": deps.format_fallback_reason(
            fallback_reasons + ([socratic_question_fallback] if socratic_question_fallback else [])
        ),
        "created_at": db_response.created_at,
    }


async def build_socratic_response_stream(
    *,
    deps: SocraticResponseSupportDeps,
    problem_id: UUID,
    response_data: ProblemResponseCreate,
    current_user: User,
    db: AsyncSession,
    problem: Problem,
) -> EventSourceResponse:
    async def event_generator():
        queue: asyncio.Queue[tuple[str, object] | None] = asyncio.Queue()

        async def on_progress(event: str, payload: dict):
            await queue.put((event, payload))

        async def worker():
            try:
                response = await complete_socratic_response(
                    deps=deps,
                    problem_id=problem_id,
                    response_data=response_data,
                    current_user=current_user,
                    db=db,
                    problem=problem,
                    on_progress=on_progress,
                )
                await queue.put(("final", jsonable_encoder(response)))
                await queue.put(("done", ""))
            except Exception:
                await db.rollback()
                await queue.put(("error", {"message": "Failed to complete streamed Socratic evaluation."}))
            finally:
                await queue.put(None)

        worker_task = asyncio.create_task(worker())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event_name, payload = item
                if event_name == "done":
                    yield {"event": "done", "data": ""}
                    continue
                yield {"event": event_name, "data": json.dumps(payload)}
        finally:
            await worker_task

    return EventSourceResponse(event_generator())
