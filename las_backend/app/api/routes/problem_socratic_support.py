import asyncio
import json
import time
import uuid
from typing import List, Optional

from fastapi.encoders import jsonable_encoder
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.problem_learning_path_support import (
    _load_active_learning_path,
    _resolve_current_step,
)
from app.core.config import get_settings
from app.models.entities.user import Problem, ProblemMasteryEvent, ProblemTurn
from app.services.model_os_service import model_os_service

settings = get_settings()


def _normalize_question_kind(raw_kind: Optional[str], default: str = "probe") -> str:
    kind = (raw_kind or default).strip().lower()
    if kind not in {"probe", "checkpoint"}:
        return default
    return kind


async def _load_latest_step_feedback(
    db: AsyncSession,
    *,
    problem_id: str,
    user_id: str,
    step_index: int,
) -> tuple[Optional[dict], Optional[ProblemMasteryEvent], list[str]]:
    latest_turn_result = await db.execute(
        select(ProblemTurn)
        .where(
            ProblemTurn.problem_id == problem_id,
            ProblemTurn.user_id == user_id,
            ProblemTurn.learning_mode == "socratic",
            ProblemTurn.step_index == step_index,
        )
        .order_by(desc(ProblemTurn.created_at))
        .limit(3)
    )
    recent_turns = latest_turn_result.scalars().all()
    latest_feedback = None
    if recent_turns and recent_turns[0].assistant_text:
        latest_feedback = model_os_service.parse_feedback_text(recent_turns[0].assistant_text)

    latest_mastery_result = await db.execute(
        select(ProblemMasteryEvent)
        .where(
            ProblemMasteryEvent.problem_id == problem_id,
            ProblemMasteryEvent.user_id == user_id,
            ProblemMasteryEvent.step_index == step_index,
        )
        .order_by(desc(ProblemMasteryEvent.created_at))
        .limit(1)
    )
    latest_mastery = latest_mastery_result.scalar_one_or_none()
    recent_answers = [turn.user_text for turn in reversed(recent_turns) if turn.user_text]
    return latest_feedback, latest_mastery, recent_answers


def _select_socratic_question_kind(
    *,
    latest_feedback: Optional[dict],
    latest_mastery: Optional[ProblemMasteryEvent],
) -> str:
    if latest_mastery is None:
        return "probe"

    mastery_score = int(getattr(latest_mastery, "mastery_score", 0) or 0)
    pass_stage = bool(getattr(latest_mastery, "pass_stage", False))
    if pass_stage or mastery_score >= 70:
        return "checkpoint"

    feedback = latest_feedback or {}
    misconception_count = len(
        [item for item in (feedback.get("misconceptions") or []) if str(item).strip()]
    )
    if mastery_score < 60 or misconception_count > 1:
        return "probe"
    return "checkpoint"


async def _resolve_socratic_question_payload(
    db: AsyncSession,
    *,
    problem: Problem,
    user_id: str,
    step_index: int,
    step_concept: str,
    step_description: str,
    provided_question_kind: Optional[str] = None,
    provided_question: Optional[str] = None,
    use_llm: bool = False,
) -> tuple[str, str, Optional[dict], Optional[ProblemMasteryEvent], List[str], Optional[str], int, int]:
    latest_feedback, latest_mastery, recent_answers = await _load_latest_step_feedback(
        db=db,
        problem_id=str(problem.id),
        user_id=user_id,
        step_index=step_index,
    )
    question_kind = _normalize_question_kind(
        provided_question_kind,
        _select_socratic_question_kind(
            latest_feedback=latest_feedback,
            latest_mastery=latest_mastery,
        ),
    )

    fallback_reason = None
    llm_calls = 0
    llm_latency_ms = 0
    question = str(provided_question or "").strip()
    if not question:
        fallback_question = model_os_service.build_socratic_question_fallback(
            step_concept=step_concept,
            question_kind=question_kind,
            latest_feedback=latest_feedback,
        )
        question = fallback_question
        if use_llm:
            llm_calls = 1
            llm_started = time.monotonic()
            try:
                generated = await asyncio.wait_for(
                    model_os_service.generate_socratic_question(
                        problem_title=problem.title,
                        problem_description=problem.description or "",
                        step_concept=step_concept,
                        step_description=step_description,
                        question_kind=question_kind,
                        recent_responses=recent_answers,
                        latest_feedback=latest_feedback,
                    ),
                    timeout=max(1, int(settings.PROBLEM_RESPONSE_TIMEOUT_SECONDS)),
                )
                if str(generated or "").strip():
                    question = str(generated).strip()
                else:
                    fallback_reason = "empty:socratic_question"
            except asyncio.TimeoutError:
                fallback_reason = "timeout:socratic_question"
            except Exception:
                fallback_reason = "error:socratic_question"
            finally:
                llm_latency_ms = int((time.monotonic() - llm_started) * 1000)

    return question_kind, question, latest_feedback, latest_mastery, recent_answers, fallback_reason, llm_calls, llm_latency_ms


def _build_socratic_mode_metadata(
    *,
    step_index: int,
    step_concept: str,
    latest_feedback: Optional[dict],
    latest_mastery: Optional[ProblemMasteryEvent],
) -> dict:
    return {
        "step_index": step_index,
        "step_concept": step_concept,
        "latest_mastery_score": int(getattr(latest_mastery, "mastery_score", 0) or 0),
        "latest_pass_stage": bool(getattr(latest_mastery, "pass_stage", False)) if latest_mastery else False,
        "latest_correctness": str((latest_feedback or {}).get("correctness") or ""),
    }


async def build_socratic_question_response_payload(
    *,
    db: AsyncSession,
    problem: Problem,
    user_id: str,
) -> dict:
    learning_path = await _load_active_learning_path(db, problem_id=str(problem.id))
    current_step_index, current_step_data = _resolve_current_step(learning_path)
    step_concept = (current_step_data or {}).get("concept") or problem.title
    step_description = (current_step_data or {}).get("description") or (problem.description or "")
    trace_id = str(uuid.uuid4())

    question_kind, question, latest_feedback, latest_mastery, _, fallback_reason, llm_calls, llm_latency_ms = (
        await _resolve_socratic_question_payload(
            db=db,
            problem=problem,
            user_id=user_id,
            step_index=current_step_index,
            step_concept=step_concept,
            step_description=step_description,
            use_llm=True,
        )
    )

    return {
        "learning_mode": "socratic",
        "step_index": current_step_index,
        "step_concept": step_concept,
        "question_kind": question_kind,
        "question": question,
        "mode_metadata": _build_socratic_mode_metadata(
            step_index=current_step_index,
            step_concept=step_concept,
            latest_feedback=latest_feedback,
            latest_mastery=latest_mastery,
        ),
        "trace_id": trace_id,
        "llm_calls": llm_calls,
        "llm_latency_ms": llm_latency_ms,
        "fallback_reason": fallback_reason,
    }


async def build_socratic_question_stream_response(
    *,
    db: AsyncSession,
    problem: Problem,
    user_id: str,
) -> EventSourceResponse:
    learning_path = await _load_active_learning_path(db, problem_id=str(problem.id))
    current_step_index, current_step_data = _resolve_current_step(learning_path)
    step_concept = (current_step_data or {}).get("concept") or problem.title
    step_description = (current_step_data or {}).get("description") or (problem.description or "")
    trace_id = str(uuid.uuid4())

    latest_feedback, latest_mastery, recent_answers = await _load_latest_step_feedback(
        db=db,
        problem_id=str(problem.id),
        user_id=user_id,
        step_index=current_step_index,
    )
    question_kind = _normalize_question_kind(
        None,
        _select_socratic_question_kind(
            latest_feedback=latest_feedback,
            latest_mastery=latest_mastery,
        ),
    )
    fallback_question = model_os_service.build_socratic_question_fallback(
        step_concept=step_concept,
        question_kind=question_kind,
        latest_feedback=latest_feedback,
    )

    async def event_generator():
        fallback_reason = None
        question_chunks: List[str] = []
        llm_calls = 1
        llm_started = time.monotonic()

        try:
            async for token in model_os_service.stream_socratic_question(
                problem_title=problem.title,
                problem_description=problem.description or "",
                step_concept=step_concept,
                step_description=step_description,
                question_kind=question_kind,
                recent_responses=recent_answers,
                latest_feedback=latest_feedback,
            ):
                if not question_chunks and token.startswith("Error:"):
                    raise RuntimeError(token)
                question_chunks.append(token)
                yield {"event": "token", "data": token}
        except Exception:
            fallback_reason = "error:socratic_question"

        llm_latency_ms = int((time.monotonic() - llm_started) * 1000)
        question = "".join(question_chunks).strip()
        if not question:
            fallback_reason = fallback_reason or "empty:socratic_question"
            question = fallback_question
            if question:
                yield {"event": "token", "data": question}

        payload = {
            "learning_mode": "socratic",
            "step_index": current_step_index,
            "step_concept": step_concept,
            "question_kind": question_kind,
            "question": question,
            "mode_metadata": _build_socratic_mode_metadata(
                step_index=current_step_index,
                step_concept=step_concept,
                latest_feedback=latest_feedback,
                latest_mastery=latest_mastery,
            ),
            "trace_id": trace_id,
            "llm_calls": llm_calls,
            "llm_latency_ms": llm_latency_ms,
            "fallback_reason": fallback_reason,
        }
        yield {"event": "final", "data": json.dumps(jsonable_encoder(payload))}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())
