import asyncio
import re
import time
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, desc, func
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
    ProblemMasteryEvent,
    ProblemConceptCandidate,
    ProblemPathCandidate,
    LearningEvent,
    Concept,
    ConceptAlias,
    ConceptEvidence,
    ConceptRelation,
    ModelCard,
    ReviewSchedule,
)
from app.schemas.problem import (
    ProblemCreate,
    ProblemUpdate,
    ProblemResponse,
    ProblemResponseCreate,
    ProblemResponseResponse,
    SocraticQuestionResponse,
    TurnEvaluationResponse,
    TurnDecisionResponse,
    TurnFollowUpResponse,
    LearningPathResponse,
    LearningPathProgressUpdate,
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
from app.services.model_os_service import model_os_service
from app.services.srs_service import srs_service

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


def _normalize_learning_path_kind(raw_kind: Optional[str], default: str = "main") -> str:
    kind = str(raw_kind or default).strip().lower()
    if kind not in {"main", "branch", "prerequisite", "comparison"}:
        return default
    return kind


async def _load_active_learning_path(db: AsyncSession, *, problem_id: str) -> Optional[LearningPath]:
    active_result = await db.execute(
        select(LearningPath)
        .where(
            LearningPath.problem_id == problem_id,
            LearningPath.is_active.is_(True),
        )
        .order_by(desc(LearningPath.updated_at), desc(LearningPath.created_at))
        .limit(1)
    )
    active_path = active_result.scalar_one_or_none()
    if active_path:
        return active_path

    main_path = await _load_main_learning_path(db, problem_id=problem_id)
    if main_path:
        main_path.is_active = True
        await db.flush()
    return main_path


async def _load_main_learning_path(db: AsyncSession, *, problem_id: str) -> Optional[LearningPath]:
    result = await db.execute(
        select(LearningPath)
        .where(
            LearningPath.problem_id == problem_id,
            LearningPath.kind == "main",
        )
        .order_by(LearningPath.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _set_active_learning_path(
    db: AsyncSession,
    *,
    problem_id: str,
    target_path_id: str,
) -> Optional[LearningPath]:
    result = await db.execute(
        select(LearningPath).where(LearningPath.problem_id == problem_id)
    )
    target_path = None
    for path in result.scalars().all():
        is_target = path.id == target_path_id
        path.is_active = is_target
        if is_target:
            target_path = path
    if target_path is None:
        return None
    await db.flush()
    return target_path


def _renumber_learning_path_steps(path_data: List[dict]) -> List[dict]:
    normalized_steps: List[dict] = []
    for index, step in enumerate(path_data or []):
        if not isinstance(step, dict):
            continue
        normalized_steps.append(
            {
                "step": index + 1,
                "concept": str(step.get("concept") or f"Step {index + 1}").strip(),
                "description": str(step.get("description") or "").strip(),
                "resources": [
                    str(resource).strip()
                    for resource in (step.get("resources") or [])
                    if str(resource).strip()
                ],
            }
        )
    return normalized_steps


def _map_candidate_type_to_learning_path_kind(path_type: str) -> str:
    normalized = _normalize_path_suggestion_type(path_type)
    if normalized == "prerequisite":
        return "prerequisite"
    if normalized == "comparison_path":
        return "comparison"
    return "branch"


def _build_path_steps_from_candidate(
    candidate: ProblemPathCandidate,
    *,
    anchor_concept: str,
) -> List[dict]:
    cjk = _contains_cjk_text(candidate.title, candidate.reason, anchor_concept)
    title = str(candidate.title or anchor_concept).strip()
    reason = str(candidate.reason or "").strip()
    path_type = _normalize_path_suggestion_type(candidate.path_type)

    if path_type == "prerequisite":
        steps = [
            {
                "concept": title,
                "description": reason or (
                    f"Build the missing foundation for '{anchor_concept}' before returning."
                    if not cjk
                    else f"先补足“{anchor_concept}”所缺的前置基础，再返回主线。"
                ),
                "resources": [anchor_concept],
            },
            {
                "concept": (
                    f"Reconnect {title} to {anchor_concept}"
                    if not cjk
                    else f"把“{title}”重新接回“{anchor_concept}”"
                ),
                "description": (
                    f"Explain how '{title}' supports the original step '{anchor_concept}'."
                    if not cjk
                    else f"说明“{title}”如何支撑原主线步骤“{anchor_concept}”。"
                ),
                "resources": [title, anchor_concept],
            },
        ]
    elif path_type == "comparison_path":
        steps = [
            {
                "concept": title,
                "description": reason or (
                    f"Clarify the comparison target around '{anchor_concept}'."
                    if not cjk
                    else f"先澄清与“{anchor_concept}”相关的对比对象。"
                ),
                "resources": [anchor_concept],
            },
            {
                "concept": (
                    f"Compare {title} with {anchor_concept}"
                    if not cjk
                    else f"对比“{title}”与“{anchor_concept}”"
                ),
                "description": (
                    f"Write side-by-side boundaries, tradeoffs, and decision cues."
                    if not cjk
                    else "并列写出两者的边界、取舍和使用判断信号。"
                ),
                "resources": [title, anchor_concept],
            },
        ]
    else:
        steps = [
            {
                "concept": title,
                "description": reason or (
                    f"Deepen the current understanding of '{anchor_concept}' with one focused branch."
                    if not cjk
                    else f"围绕“{anchor_concept}”开一条聚焦深挖支线。"
                ),
                "resources": [anchor_concept],
            },
            {
                "concept": (
                    f"Stress-test {anchor_concept}"
                    if not cjk
                    else f"用边界案例检验“{anchor_concept}”"
                ),
                "description": (
                    f"Use one example or edge case to consolidate the branch and prepare to return."
                    if not cjk
                    else "用一个例子或边界案例巩固理解，并准备返回主线。"
                ),
                "resources": [title, anchor_concept],
            },
        ]
    return _renumber_learning_path_steps(steps)


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


def _normalize_question_kind(raw_kind: Optional[str], default: str = "probe") -> str:
    kind = (raw_kind or default).strip().lower()
    if kind not in {"probe", "checkpoint"}:
        return default
    return kind


def _contains_cjk_text(*texts: Optional[str]) -> bool:
    return any(bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", str(text or ""))) for text in texts)


def _normalize_exploration_answer_type(
    raw_type: Optional[str],
    default: str = "concept_explanation",
) -> str:
    answer_type = str(raw_type or default).strip().lower().replace(" ", "_")
    if answer_type not in {
        "concept_explanation",
        "boundary_clarification",
        "misconception_correction",
        "comparison",
        "prerequisite_explanation",
        "worked_example",
    }:
        return default
    return answer_type


def _normalize_path_suggestion_type(
    raw_type: Optional[str],
    default: str = "branch_deep_dive",
) -> str:
    path_type = str(raw_type or default).strip().lower().replace(" ", "_")
    if path_type not in {"prerequisite", "branch_deep_dive", "comparison_path"}:
        return default
    return path_type


def _infer_exploration_answer_type(question: str) -> str:
    text = str(question or "").strip().casefold()
    if any(marker in text for marker in ["difference between", "compare", "versus", " vs ", "区别", "对比"]):
        return "comparison"
    if any(marker in text for marker in ["before", "prerequisite", "prereq", "先学", "前置", "基础"]):
        return "prerequisite_explanation"
    if any(marker in text for marker in ["example", "walk through", "worked example", "举例", "例子", "演示"]):
        return "worked_example"
    if any(marker in text for marker in ["misconception", "wrong", "误解", "错误", "confused", "是不是"]):
        return "misconception_correction"
    if any(marker in text for marker in ["boundary", "edge case", "when should", "when not", "边界", "什么时候不"]):
        return "boundary_clarification"
    return "concept_explanation"


def _sanitize_question_concept_phrase(raw: Optional[str]) -> str:
    phrase = re.sub(r"\s+", " ", str(raw or "")).strip(" \t\r\n,.;:!?\"'()[]{}")
    phrase = re.sub(r"^(the|a|an)\s+", "", phrase, flags=re.IGNORECASE)
    return phrase.strip()


def _extract_comparison_targets_from_question(question: str) -> List[str]:
    text = str(question or "").strip()
    if not text:
        return []

    patterns = [
        r"(?:difference between|compare)\s+(?P<left>.+?)\s+(?:and|with|to|vs\.?|versus)\s+(?P<right>.+?)(?:\s+when\b|\s+if\b|\s+under\b|\s+for\b|[?.!,]|$)",
        r"(?P<left>.+?)\s+(?:vs\.?|versus)\s+(?P<right>.+?)(?:\s+when\b|\s+if\b|\s+under\b|\s+for\b|[?.!,]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        left = _sanitize_question_concept_phrase(match.group("left"))
        right = _sanitize_question_concept_phrase(match.group("right"))
        concepts = model_os_service.normalize_concepts([left, right], limit=2)
        if len(concepts) >= 2:
            return concepts
    return []


def _find_question_concept_mentions(question: str, candidate_concepts: List[str]) -> List[str]:
    question_key = model_os_service.normalize_concept_key(question)
    question_text = str(question or "")
    matches: List[tuple[int, int, str]] = []
    for concept in model_os_service.normalize_concepts(candidate_concepts, limit=10):
        concept_key = model_os_service.normalize_concept_key(concept)
        if not concept_key or concept_key not in question_key:
            continue
        position = question_text.casefold().find(str(concept).casefold())
        matches.append((position if position >= 0 else 10_000, -len(concept), concept))
    matches.sort(key=lambda item: (item[0], item[1]))
    return [concept for _position, _neg_len, concept in matches]


def _derive_question_concepts(
    *,
    question: str,
    answer_type: str,
    candidate_concepts: List[str],
) -> List[str]:
    mentioned = _find_question_concept_mentions(question, candidate_concepts)
    if answer_type == "comparison" and len(mentioned) >= 2:
        return model_os_service.normalize_concepts(mentioned[:2], limit=2)
    if answer_type != "comparison" and mentioned:
        return model_os_service.normalize_concepts(mentioned[:1], limit=1)

    if answer_type == "comparison":
        extracted = _extract_comparison_targets_from_question(question)
        if extracted:
            return extracted
    return []


def _filter_grounded_ask_concepts(
    *,
    question: str,
    answer: str,
    ask_concepts: List[str],
    question_concepts: List[str],
    step_concept: str,
) -> List[str]:
    concepts = model_os_service.normalize_concepts(ask_concepts, limit=8)
    if not question_concepts:
        return concepts

    grounded_text = model_os_service.normalize_concept_key(f"{question}\n{answer}")
    step_key = model_os_service.normalize_concept_key(step_concept)
    filtered: List[str] = []
    for concept in concepts:
        concept_key = model_os_service.normalize_concept_key(concept)
        if not concept_key:
            continue
        if concept_key == step_key:
            continue
        if concept_key in grounded_text:
            filtered.append(concept)
    return filtered


def _pick_secondary_concept(
    *,
    primary: str,
    answered_concepts: List[str],
    related_concepts: List[str],
    step_concept: str,
) -> str:
    primary_key = model_os_service.normalize_concept_key(primary)
    for concept in [*answered_concepts[1:], *related_concepts, step_concept]:
        concept_key = model_os_service.normalize_concept_key(concept)
        if concept_key and concept_key != primary_key:
            return concept
    return step_concept or primary


def _select_answered_concepts(
    *,
    question: str,
    step_concept: str,
    inferred_concepts: List[str],
    answer_type: str,
    question_concepts: Optional[List[str]] = None,
) -> List[str]:
    prioritized = model_os_service.normalize_concepts(question_concepts or [], limit=2)
    if answer_type == "comparison" and len(prioritized) >= 2:
        return prioritized[:2]
    if answer_type != "comparison" and prioritized:
        return prioritized[:1]

    concept_pool = model_os_service.normalize_concepts(
        [*inferred_concepts, step_concept],
        limit=6,
    )
    if not concept_pool:
        return model_os_service.normalize_concepts([step_concept], limit=1)

    question_key = model_os_service.normalize_concept_key(question)
    mentioned = []
    for concept in concept_pool:
        concept_key = model_os_service.normalize_concept_key(concept)
        if concept_key and concept_key in question_key:
            mentioned.append(concept)

    if answer_type == "comparison":
        selected = mentioned[:2] or concept_pool[:2]
    else:
        selected = mentioned[:1] or concept_pool[:1]
    return model_os_service.normalize_concepts(selected or [step_concept], limit=2)


def _select_related_concepts(
    *,
    answered_concepts: List[str],
    step_concept: str,
    inferred_concepts: List[str],
) -> List[str]:
    concept_pool = model_os_service.normalize_concepts(
        [*inferred_concepts, step_concept],
        limit=8,
    )
    answered_keys = {
        model_os_service.normalize_concept_key(item)
        for item in answered_concepts
        if model_os_service.normalize_concept_key(item)
    }
    return [
        concept
        for concept in concept_pool
        if model_os_service.normalize_concept_key(concept) not in answered_keys
    ][:4]


def _build_exploration_next_actions(
    *,
    answer_type: str,
    question: str,
    step_concept: str,
    answered_concepts: List[str],
    related_concepts: List[str],
) -> List[str]:
    cjk = _contains_cjk_text(question, step_concept, *answered_concepts, *related_concepts)
    primary = answered_concepts[0] if answered_concepts else step_concept or "this concept"
    secondary = _pick_secondary_concept(
        primary=primary,
        answered_concepts=answered_concepts,
        related_concepts=related_concepts,
        step_concept=step_concept or primary,
    )

    if cjk:
        if answer_type == "comparison":
            return [
                f"用 2-3 句话对比“{primary}”和“{secondary}”的关键区别。",
                f"分别写一个场景，说明什么时候该用“{primary}”或“{secondary}”。",
                "回到当前主线步骤，判断现在真正需要哪个概念。",
            ]
        if answer_type == "prerequisite_explanation":
            return [
                f"先补“{secondary}”的基础定义和一个最小例子。",
                f"再重述“{primary}”与当前学习步骤的关系。",
                "确认补完前置后是否可以回到主线继续推进。",
            ]
        if answer_type == "worked_example":
            return [
                f"围绕“{primary}”手写一个最小 worked example。",
                "标出每一步为什么成立，而不是只写结论。",
                f"再把这个例子映射回当前步骤“{step_concept}”。",
            ]
        if answer_type == "misconception_correction":
            return [
                f"先写出你之前对“{primary}”最容易混淆的一点。",
                "用一个反例说明错误理解为什么会失败。",
                "回到当前步骤，重写一版更准确的表述。",
            ]
        if answer_type == "boundary_clarification":
            return [
                f"列出“{primary}”成立与不成立的边界条件。",
                f"补一个“{primary}”失效的反例。",
                "确认这些边界会如何影响当前主线步骤。",
            ]
        return [
            f"先用你自己的话重新解释“{primary}”。",
            f"再把它和“{secondary}”做一个简短区分。",
            f"最后说明它在当前步骤“{step_concept}”里起什么作用。",
        ]

    if answer_type == "comparison":
        return [
            f"Write a 2-3 sentence comparison between '{primary}' and '{secondary}'.",
            f"Give one case where '{primary}' is the better fit and one for '{secondary}'.",
            "Return to the current step and decide which concept matters now.",
        ]
    if answer_type == "prerequisite_explanation":
        return [
            f"Review the basic definition of '{secondary}' and one minimal example.",
            f"Restate how '{primary}' depends on that prerequisite.",
            "Decide whether you can return to the main path after that review.",
        ]
    if answer_type == "worked_example":
        return [
            f"Work through one minimal example for '{primary}'.",
            "Annotate why each step is valid instead of only writing the result.",
            f"Map that example back to the current step '{step_concept}'.",
        ]
    if answer_type == "misconception_correction":
        return [
            f"Write down the misconception you had about '{primary}'.",
            "Add one counter-example that breaks the incorrect version.",
            "Rewrite your explanation using the corrected framing.",
        ]
    if answer_type == "boundary_clarification":
        return [
            f"List the conditions where '{primary}' applies and where it does not.",
            f"Add one edge case that exposes the boundary of '{primary}'.",
            f"Check how that boundary affects the current step '{step_concept}'.",
        ]
    return [
        f"Restate '{primary}' in your own words.",
        f"Contrast it briefly with '{secondary}'.",
        f"Explain how it helps with the current step '{step_concept}'.",
    ]


def _build_exploration_path_suggestions(
    *,
    answer_type: str,
    question: str,
    step_concept: str,
    answered_concepts: List[str],
    related_concepts: List[str],
) -> List[dict]:
    cjk = _contains_cjk_text(question, step_concept, *answered_concepts, *related_concepts)
    primary = answered_concepts[0] if answered_concepts else step_concept or "this concept"
    secondary = _pick_secondary_concept(
        primary=primary,
        answered_concepts=answered_concepts,
        related_concepts=related_concepts,
        step_concept=step_concept or primary,
    )

    suggestions: List[dict] = []
    if answer_type == "prerequisite_explanation":
        suggestions.append(
            {
                "type": "prerequisite",
                "title": (
                    f"先补“{secondary}”，再回到“{primary}”"
                    if cjk
                    else f"Study '{secondary}' before returning to '{primary}'"
                ),
                "reason": (
                    f"这个问题暴露了对“{primary}”前置知识的依赖。"
                    if cjk
                    else f"This question suggests '{primary}' depends on prerequisite knowledge first."
                ),
            }
        )
    elif answer_type == "comparison":
        suggestions.append(
            {
                "type": "comparison_path",
                "title": (
                    f"开一条“{primary} vs {secondary}”对比支线"
                    if cjk
                    else f"Open a comparison path for '{primary}' vs '{secondary}'"
                ),
                "reason": (
                    "这类问题更适合通过并列比较来稳定边界。"
                    if cjk
                    else "A short comparison branch will make the boundary between the two concepts clearer."
                ),
            }
        )
    elif answer_type == "worked_example":
        suggestions.append(
            {
                "type": "branch_deep_dive",
                "title": (
                    f"围绕“{primary}”做一个例题深挖"
                    if cjk
                    else f"Open a worked-example deep dive for '{primary}'"
                ),
                "reason": (
                    "这个问题更适合通过具体例子固化理解。"
                    if cjk
                    else "A worked-example branch would likely consolidate this explanation faster."
                ),
            }
        )

    normalized_suggestions = []
    for suggestion in suggestions:
        normalized_suggestions.append(
            {
                "type": _normalize_path_suggestion_type(suggestion.get("type")),
                "title": str(suggestion.get("title") or "").strip(),
                "reason": str(suggestion.get("reason") or "").strip() or None,
            }
        )
    return normalized_suggestions


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

    normalized_inputs = model_os_service.normalize_concepts(inferred_concepts, limit=max_candidates)
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
        has_same_path_candidate = False
        if source_path_id:
            has_same_path_candidate = (normalized, source_path_id) in existing_candidate_contexts
        else:
            has_same_path_candidate = any(
                candidate_key == normalized
                for candidate_key, _candidate_path_id in existing_candidate_contexts
            )

        # Preserve one candidate artifact per path context so weak recall can route
        # back into the branch where the concept was actually explored.
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
        existing_candidate_contexts.add((normalized, source_path_id or None))

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


def _default_path_insertion(path_type: str) -> str:
    normalized = _normalize_path_suggestion_type(path_type)
    if normalized == "prerequisite":
        return "insert_before_current_main"
    if normalized in {"branch_deep_dive", "comparison_path"}:
        return "save_as_side_branch"
    return "bookmark_for_later"


def _normalize_path_insertion(action: Optional[str], default: str = "bookmark_for_later") -> str:
    normalized = str(action or default).strip().lower()
    if normalized not in {"insert_before_current_main", "save_as_side_branch", "bookmark_for_later"}:
        return default
    return normalized


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


def _serialize_problem_path_candidate(candidate: ProblemPathCandidate) -> dict:
    return {
        "id": candidate.id,
        "problem_id": candidate.problem_id,
        "learning_mode": _normalize_learning_mode(candidate.learning_mode, "socratic"),
        "source_turn_id": candidate.source_turn_id,
        "step_index": candidate.step_index,
        "type": _normalize_path_suggestion_type(candidate.path_type),
        "title": candidate.title,
        "reason": candidate.reason,
        "recommended_insertion": _normalize_path_insertion(candidate.recommended_insertion),
        "selected_insertion": (
            _normalize_path_insertion(candidate.selected_insertion)
            if candidate.selected_insertion
            else None
        ),
        "status": str(candidate.status or "pending"),
        "evidence_snippet": candidate.evidence_snippet,
        "reviewed_at": candidate.reviewed_at.isoformat() if candidate.reviewed_at else None,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
    }


def _candidate_model_card_title(candidate: ProblemConceptCandidate) -> str:
    return str(candidate.merged_into_concept or candidate.concept_text or "").strip()


def _candidate_model_card_notes(problem: Problem, candidate: ProblemConceptCandidate) -> str:
    title = _candidate_model_card_title(candidate)
    source_turn_preview = _build_turn_preview(getattr(candidate, "source_turn", None))
    lines = [
        f"Promoted from problem: {problem.title}",
        f"Source learning mode: {_normalize_learning_mode(candidate.learning_mode, 'socratic')}",
    ]
    if source_turn_preview:
        lines.append(f"Source turn: {source_turn_preview}")
    if candidate.evidence_snippet:
        lines.append(f"Evidence: {candidate.evidence_snippet}")
    lines.append(f"Promoted concept: {title}")
    return "\n".join(lines)


async def _load_candidate_review_schedule(
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


async def _ensure_model_card_for_candidate(
    db: AsyncSession,
    *,
    user_id: str,
    problem: Problem,
    candidate: ProblemConceptCandidate,
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
        candidate.linked_model_card_id = str(existing_card.id)
        await db.flush()
        return existing_card, False

    notes = _candidate_model_card_notes(problem, candidate)
    examples = model_os_service.normalize_concepts(
        [candidate.concept_text, problem.title, *(problem.associated_concepts or [])],
        limit=3,
    )
    model_card = ModelCard(
        user_id=user_id,
        title=target_title,
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


def _serialize_problem_concept_candidate_handoff(
    *,
    candidate: ProblemConceptCandidate,
    model_card: ModelCard,
    created_model_card: bool,
    review_schedule: Optional[ReviewSchedule],
    trace_id: str,
) -> dict:
    return {
        "candidate": _serialize_problem_concept_candidate(candidate),
        "model_card": model_card,
        "created_model_card": created_model_card,
        "review_scheduled": review_schedule is not None,
        "next_review_at": review_schedule.next_review_at.isoformat() if review_schedule else None,
        "trace_id": trace_id,
    }


async def _register_problem_path_candidates(
    db: AsyncSession,
    *,
    user_id: str,
    problem_id: str,
    learning_mode: str,
    source_turn_id: str,
    step_index: int,
    candidate_specs: List[dict],
    evidence_snippet: Optional[str],
) -> List[dict]:
    if not candidate_specs:
        return []

    existing_rows = await db.execute(
        select(ProblemPathCandidate.path_type, ProblemPathCandidate.normalized_title)
        .where(
            ProblemPathCandidate.user_id == user_id,
            ProblemPathCandidate.problem_id == problem_id,
            ProblemPathCandidate.status.in_(["pending", "planned", "bookmarked"]),
        )
    )
    existing_keys = {
        (str(row[0] or ""), str(row[1] or ""))
        for row in existing_rows.all()
        if row[0] and row[1]
    }

    created: List[ProblemPathCandidate] = []
    for spec in candidate_specs:
        path_type = _normalize_path_suggestion_type(spec.get("type"))
        title = re.sub(r"\s+", " ", str(spec.get("title") or "")).strip()[:200]
        if not title:
            continue
        normalized_title = model_os_service.normalize_concept_key(title)
        if not normalized_title:
            continue
        dedupe_key = (path_type, normalized_title)
        if dedupe_key in existing_keys:
            continue

        recommended_insertion = _normalize_path_insertion(
            spec.get("recommended_insertion"),
            _default_path_insertion(path_type),
        )
        candidate = ProblemPathCandidate(
            user_id=user_id,
            problem_id=problem_id,
            learning_mode=_normalize_learning_mode(learning_mode, "socratic"),
            source_turn_id=source_turn_id,
            step_index=step_index,
            path_type=path_type,
            title=title,
            normalized_title=normalized_title,
            reason=str(spec.get("reason") or "").strip() or None,
            recommended_insertion=recommended_insertion,
            status="pending",
            evidence_snippet=(evidence_snippet or "")[:500] or None,
        )
        db.add(candidate)
        created.append(candidate)
        existing_keys.add(dedupe_key)

    if created:
        await db.flush()
    return [_serialize_problem_path_candidate(item) for item in created]


def _build_socratic_path_candidate_specs(
    *,
    step_concept: str,
    question_kind: str,
    structured_feedback: dict,
    auto_advanced: bool,
) -> List[dict]:
    if auto_advanced:
        return []

    mastery_score = int(structured_feedback.get("mastery_score") or 0)
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
    decision_reason = str(structured_feedback.get("decision_reason") or "").strip()
    joined_text = " ".join([next_question, *suggestions, *misconceptions]).casefold()
    cjk = _contains_cjk_text(step_concept, next_question, decision_reason, *misconceptions, *suggestions)

    candidate_specs: List[dict] = []
    if mastery_score < 60 or misconceptions:
        candidate_specs.append(
            {
                "type": "prerequisite",
                "title": (
                    f"先补“{step_concept}”的前置基础"
                    if cjk
                    else f"Fill prerequisite foundations for '{step_concept}' first"
                ),
                "reason": (
                    misconceptions[0]
                    if misconceptions
                    else (
                        f"Current mastery on '{step_concept}' is not stable enough for progression."
                        if not cjk
                        else f"当前对“{step_concept}”的掌握还不稳定，不适合直接推进。"
                    )
                ),
                "recommended_insertion": "insert_before_current_main",
            }
        )
    elif question_kind == "checkpoint" and mastery_score < 85:
        candidate_specs.append(
            {
                "type": "branch_deep_dive",
                "title": (
                    f"围绕“{step_concept}”开一条深挖支线"
                    if cjk
                    else f"Open a deep-dive branch for '{step_concept}'"
                ),
                "reason": decision_reason or (
                    "A short side branch would help consolidate this step before progression."
                    if not cjk
                    else "在推进前先做一条短支线深挖，会更容易把这一步打稳。"
                ),
                "recommended_insertion": "save_as_side_branch",
            }
        )

    if any(marker in joined_text for marker in ["difference", "compare", "versus", "区别", "对比"]):
        candidate_specs.append(
            {
                "type": "comparison_path",
                "title": (
                    f"为“{step_concept}”补一条对比路径"
                    if cjk
                    else f"Add a comparison path around '{step_concept}'"
                ),
                "reason": next_question or (
                    "Comparison-focused follow-up would likely clarify this concept boundary."
                    if not cjk
                    else "当前更适合通过对比来澄清这个概念的边界。"
                ),
                "recommended_insertion": "save_as_side_branch",
            }
        )
    return candidate_specs[:2]


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
        associated_concepts=associated_concepts,
        timeout_seconds=settings.LEARNING_PATH_TIMEOUT_SECONDS,
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

    learning_path = await _load_active_learning_path(db, problem_id=str(problem_id))
    current_step_index, current_step_data = _resolve_current_step(learning_path)
    step_concept = (current_step_data or {}).get("concept") or problem.title
    step_description = (current_step_data or {}).get("description") or (problem.description or "")
    trace_id = str(uuid.uuid4())

    question_kind, question, latest_feedback, latest_mastery, _, fallback_reason, llm_calls, llm_latency_ms = (
        await _resolve_socratic_question_payload(
            db=db,
            problem=problem,
            user_id=str(current_user.id),
            step_index=current_step_index,
            step_concept=step_concept,
            step_description=step_description,
            use_llm=True,
        )
    )

    mode_metadata = {
        "step_index": current_step_index,
        "step_concept": step_concept,
        "latest_mastery_score": int(getattr(latest_mastery, "mastery_score", 0) or 0),
        "latest_pass_stage": bool(getattr(latest_mastery, "pass_stage", False)) if latest_mastery else False,
        "latest_correctness": str((latest_feedback or {}).get("correctness") or ""),
    }
    return {
        "learning_mode": "socratic",
        "step_index": current_step_index,
        "step_concept": step_concept,
        "question_kind": question_kind,
        "question": question,
        "mode_metadata": mode_metadata,
        "trace_id": trace_id,
        "llm_calls": llm_calls,
        "llm_latency_ms": llm_latency_ms,
        "fallback_reason": fallback_reason,
    }


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

    evidence_snippet = _build_concept_evidence_snippet(response_data.user_response, step_concept)
    accepted_concepts, pending_concepts = await _register_problem_concept_candidates(
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
    derived_path_candidates = await _register_problem_path_candidates(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem_id),
        learning_mode=learning_mode,
        source_turn_id=str(db_turn.id),
        step_index=current_step_index,
        candidate_specs=_build_socratic_path_candidate_specs(
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

    await _log_learning_event(
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
        "fallback_reason": _format_fallback_reason(
            fallback_reasons + ([socratic_question_fallback] if socratic_question_fallback else [])
        ),
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
    return [_serialize_problem_path_candidate(item) for item in result.scalars().all()]


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
    previous_status = str(candidate.status or "")
    previous_selected_insertion = str(candidate.selected_insertion or "")
    previous_reviewed_at = candidate.reviewed_at
    applied_path_id: Optional[str] = None
    if action == "dismiss":
        candidate.status = "dismissed"
        candidate.selected_insertion = None
    elif action == "bookmark_for_later":
        candidate.status = "bookmarked"
        candidate.selected_insertion = "bookmark_for_later"
    elif action in {"insert_before_current_main", "save_as_side_branch"}:
        candidate.status = "planned"
        candidate.selected_insertion = _normalize_path_insertion(action)
        if action == "insert_before_current_main":
            if previous_reviewed_at and previous_selected_insertion == action and previous_status == "planned":
                main_path = await _load_main_learning_path(db, problem_id=str(problem_id))
                if main_path:
                    await _set_active_learning_path(
                        db=db,
                        problem_id=str(problem_id),
                        target_path_id=str(main_path.id),
                    )
                    applied_path_id = str(main_path.id)
            else:
                main_path = await _load_main_learning_path(db, problem_id=str(problem_id))
                if not main_path:
                    raise HTTPException(status_code=404, detail="Main learning path not found")
                main_step_index, main_step_data = _resolve_current_step(main_path)
                anchor_concept = (main_step_data or {}).get("concept") or problem.title
                inserted_steps = _build_path_steps_from_candidate(candidate, anchor_concept=anchor_concept)
                existing_steps = list(main_path.path_data or [])
                insert_at = min(max(int(main_path.current_step or 0), 0), len(existing_steps))
                main_path.path_data = _renumber_learning_path_steps(
                    existing_steps[:insert_at] + inserted_steps + existing_steps[insert_at:]
                )
                main_path.current_step = insert_at
                main_path.title = main_path.title or problem.title
                await _set_active_learning_path(
                    db=db,
                    problem_id=str(problem_id),
                    target_path_id=str(main_path.id),
                )
                applied_path_id = str(main_path.id)
        else:
            existing_branch_result = await db.execute(
                select(LearningPath).where(
                    LearningPath.problem_id == str(problem_id),
                    LearningPath.source_turn_id == candidate.source_turn_id,
                    LearningPath.title == candidate.title,
                    LearningPath.kind == _map_candidate_type_to_learning_path_kind(candidate.path_type),
                )
            )
            branch_path = existing_branch_result.scalar_one_or_none()
            if branch_path is None:
                active_path = await _load_active_learning_path(db, problem_id=str(problem_id))
                if not active_path:
                    raise HTTPException(status_code=404, detail="Active learning path not found")
                active_step_index, active_step_data = _resolve_current_step(active_path)
                anchor_concept = (active_step_data or {}).get("concept") or problem.title
                branch_path = LearningPath(
                    problem_id=str(problem_id),
                    title=candidate.title,
                    kind=_map_candidate_type_to_learning_path_kind(candidate.path_type),
                    parent_path_id=str(active_path.id),
                    source_turn_id=candidate.source_turn_id,
                    return_step_id=active_step_index,
                    branch_reason=candidate.reason,
                    is_active=True,
                    path_data=_build_path_steps_from_candidate(candidate, anchor_concept=anchor_concept),
                    current_step=0,
                )
                db.add(branch_path)
                await db.flush()
            await _set_active_learning_path(
                db=db,
                problem_id=str(problem_id),
                target_path_id=str(branch_path.id),
            )
            applied_path_id = str(branch_path.id)
    else:
        raise HTTPException(status_code=400, detail="Unsupported path candidate action")
    candidate.reviewed_at = datetime.utcnow()

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
            "applied_path_id": applied_path_id,
        },
    )

    await db.commit()
    await db.refresh(candidate)
    return {
        "candidate": _serialize_problem_path_candidate(candidate),
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

    candidate.status = "accepted"
    candidate.merged_into_concept = None
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
    refreshed_result = await db.execute(
        select(ProblemConceptCandidate)
        .options(selectinload(ProblemConceptCandidate.source_turn))
        .where(ProblemConceptCandidate.id == str(candidate.id))
    )
    refreshed_candidate = refreshed_result.scalar_one()
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

    candidate.status = "rejected"
    candidate.merged_into_concept = None
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
    refreshed_result = await db.execute(
        select(ProblemConceptCandidate)
        .options(selectinload(ProblemConceptCandidate.source_turn))
        .where(ProblemConceptCandidate.id == str(candidate.id))
    )
    refreshed_candidate = refreshed_result.scalar_one()
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

    normalized_target = model_os_service.normalize_concepts([payload.target_concept_text], limit=1)
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
                Concept.user_id == str(current_user.id),
                Concept.normalized_name == target_key,
            )
        )
        target_exists = concept_result.scalar_one_or_none() is not None
    if not target_exists:
        alias_result = await db.execute(
            select(ConceptAlias)
            .join(Concept, Concept.id == ConceptAlias.concept_id)
            .where(
                Concept.user_id == str(current_user.id),
                ConceptAlias.normalized_alias == target_key,
            )
        )
        target_exists = alias_result.scalar_one_or_none() is not None
    if not target_exists:
        raise HTTPException(status_code=400, detail="Merge target must already exist")

    target_concept_result = await db.execute(
        select(Concept).where(
            Concept.user_id == str(current_user.id),
            Concept.normalized_name == target_key,
        )
    )
    target_concept = target_concept_result.scalar_one_or_none()
    if target_concept is None:
        alias_concept_result = await db.execute(
            select(Concept)
            .join(ConceptAlias, Concept.id == ConceptAlias.concept_id)
            .where(
                Concept.user_id == str(current_user.id),
                ConceptAlias.normalized_alias == target_key,
            )
        )
        target_concept = alias_concept_result.scalar_one_or_none()
    if target_concept is None:
        target_concept = await _ensure_concept_record(
            db=db,
            user_id=str(current_user.id),
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
    if alias_result.scalar_one_or_none() is None:
        db.add(
            ConceptAlias(
                concept_id=target_concept.id,
                alias=candidate.concept_text,
                normalized_alias=candidate.normalized_text,
            )
        )

    db.add(
        ConceptEvidence(
            user_id=str(current_user.id),
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
    candidate.reviewer_id = str(current_user.id)
    candidate.reviewed_at = datetime.utcnow()

    await _log_learning_event(
        db=db,
        user_id=str(current_user.id),
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

    await db.commit()
    refreshed_result = await db.execute(
        select(ProblemConceptCandidate)
        .options(selectinload(ProblemConceptCandidate.source_turn))
        .where(ProblemConceptCandidate.id == str(candidate.id))
    )
    refreshed_candidate = refreshed_result.scalar_one()
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

    candidate.status = "postponed"
    candidate.merged_into_concept = None
    candidate.reviewer_id = str(current_user.id)
    candidate.reviewed_at = datetime.utcnow()

    await _log_learning_event(
        db=db,
        user_id=str(current_user.id),
        problem_id=str(problem_id),
        event_type="concept_candidate_postponed",
        learning_mode=candidate.learning_mode,
        trace_id=trace_id,
        payload={
            "candidate_id": str(candidate.id),
            "concept_text": candidate.concept_text,
            "confidence": candidate.confidence,
        },
    )

    await db.commit()
    refreshed_result = await db.execute(
        select(ProblemConceptCandidate)
        .options(selectinload(ProblemConceptCandidate.source_turn))
        .where(ProblemConceptCandidate.id == str(candidate.id))
    )
    refreshed_candidate = refreshed_result.scalar_one()
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

    model_card, created_model_card = await _ensure_model_card_for_candidate(
        db=db,
        user_id=str(current_user.id),
        problem=problem,
        candidate=candidate,
    )
    review_schedule = await _load_candidate_review_schedule(
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
    return _serialize_problem_concept_candidate_handoff(
        candidate=candidate,
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

    model_card, created_model_card = await _ensure_model_card_for_candidate(
        db=db,
        user_id=str(current_user.id),
        problem=problem,
        candidate=candidate,
    )
    review_schedule = await _load_candidate_review_schedule(
        db=db,
        user_id=str(current_user.id),
        model_card_id=str(model_card.id),
    )
    if review_schedule is None:
        review_schedule = srs_service.schedule_card(str(model_card.id), str(current_user.id))
        db.add(review_schedule)
        await db.flush()

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
    return _serialize_problem_concept_candidate_handoff(
        candidate=candidate,
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
    filtered_ask_concepts = _filter_grounded_ask_concepts(
        question=payload.question,
        answer=answer,
        ask_concepts=ask_concepts,
        question_concepts=question_concepts,
        step_concept=step_concept,
    )
    candidate_concepts = model_os_service.normalize_concepts(
        [*question_concepts, *filtered_ask_concepts],
        limit=max(3, int(settings.PROBLEM_CONCEPT_MAX_CANDIDATES_PER_TURN)),
    ) or [step_concept]
    accepted_concepts, pending_concepts = await _register_problem_concept_candidates(
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
    derived_path_candidates = await _register_problem_path_candidates(
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
        "llm_calls": llm_calls,
        "llm_latency_ms": llm_latency_ms,
        "fallback_reason": _format_fallback_reason(fallback_reasons),
    }


@router.get("/{problem_id}/learning-paths", response_model=List[LearningPathResponse])
async def list_learning_paths(
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
    if not problem_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Problem not found")

    result = await db.execute(
        select(LearningPath)
        .where(LearningPath.problem_id == str(problem_id))
        .order_by(LearningPath.created_at.asc())
    )
    paths = list(result.scalars().all())
    paths.sort(
        key=lambda item: (
            0 if _normalize_learning_path_kind(item.kind, "main") == "main" else 1,
            0 if bool(getattr(item, "is_active", False)) else 1,
            getattr(item, "created_at", datetime.utcnow()),
        )
    )
    return paths


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

    learning_path = await _load_active_learning_path(db, problem_id=str(problem_id))

    if not learning_path:
        raise HTTPException(status_code=404, detail="Learning path not found")

    return learning_path


@router.post("/{problem_id}/learning-paths/{path_id}/activate", response_model=LearningPathResponse)
async def activate_learning_path(
    problem_id: UUID,
    path_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    path_result = await db.execute(
        select(LearningPath)
        .join(Problem, Problem.id == LearningPath.problem_id)
        .where(
            LearningPath.id == str(path_id),
            LearningPath.problem_id == str(problem_id),
            Problem.user_id == str(current_user.id),
        )
    )
    target_path = path_result.scalar_one_or_none()
    if not target_path:
        raise HTTPException(status_code=404, detail="Learning path not found")

    target_path = await _set_active_learning_path(
        db=db,
        problem_id=str(problem_id),
        target_path_id=str(path_id),
    )
    await db.commit()
    await db.refresh(target_path)
    return target_path


@router.post("/{problem_id}/learning-path/return", response_model=LearningPathResponse)
async def return_to_parent_learning_path(
    problem_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    path_result = await db.execute(
        select(LearningPath)
        .join(Problem, Problem.id == LearningPath.problem_id)
        .where(
            LearningPath.problem_id == str(problem_id),
            LearningPath.is_active.is_(True),
            Problem.user_id == str(current_user.id),
        )
    )
    active_path = path_result.scalar_one_or_none()
    if not active_path:
        raise HTTPException(status_code=404, detail="Active learning path not found")
    if not active_path.parent_path_id:
        raise HTTPException(status_code=400, detail="Current path has no parent path")

    parent_result = await db.execute(
        select(LearningPath).where(
            LearningPath.id == active_path.parent_path_id,
            LearningPath.problem_id == str(problem_id),
        )
    )
    parent_path = parent_result.scalar_one_or_none()
    if not parent_path:
        raise HTTPException(status_code=404, detail="Parent learning path not found")

    if active_path.return_step_id is not None:
        total_steps = len(parent_path.path_data or [])
        parent_path.current_step = min(max(active_path.return_step_id, 0), total_steps)

    parent_path = await _set_active_learning_path(
        db=db,
        problem_id=str(problem_id),
        target_path_id=str(parent_path.id),
    )
    await db.commit()
    await db.refresh(parent_path)
    return parent_path


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

    learning_path = await _load_active_learning_path(db, problem_id=str(problem_id))
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
