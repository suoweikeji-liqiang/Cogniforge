import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.problem_learning_path_support import (
    _build_path_steps_from_candidate,
    _contains_cjk_text,
    _default_path_insertion,
    _load_active_learning_path,
    _load_main_learning_path,
    _map_candidate_type_to_learning_path_kind,
    _normalize_path_insertion,
    _normalize_path_suggestion_type,
    _resolve_current_step,
    _set_active_learning_path,
)
from app.models.entities.user import LearningPath, Problem, ProblemPathCandidate
from app.services.model_os_service import model_os_service


def _normalize_learning_mode(raw_mode: Optional[str], default: str = "socratic") -> str:
    mode = (raw_mode or default).strip().lower()
    if mode not in {"socratic", "exploration"}:
        return default
    return mode


def _build_prerequisite_candidate_title(step_concept: str, cjk: bool) -> str:
    concept = re.sub(r"\s+", " ", str(step_concept or "")).strip().strip("\"'“”")
    concept = concept or ("当前主题" if cjk else "the current topic")
    if cjk:
        return f"{concept}前置基础"
    return f"Prerequisites for '{concept}'"


def serialize_problem_path_candidate(candidate: ProblemPathCandidate) -> dict:
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


async def register_problem_path_candidates(
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
    return [serialize_problem_path_candidate(item) for item in created]


def build_socratic_path_candidate_specs(
    *,
    step_concept: str,
    question_kind: str,
    structured_feedback: dict,
    auto_advanced: bool,
    context_texts: Optional[List[str]] = None,
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
    cjk = _contains_cjk_text(
        step_concept,
        next_question,
        decision_reason,
        *misconceptions,
        *suggestions,
        *(context_texts or []),
    )

    candidate_specs: List[dict] = []
    if mastery_score < 60 or misconceptions:
        candidate_specs.append(
            {
                "type": "prerequisite",
                "title": _build_prerequisite_candidate_title(step_concept, cjk),
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


@dataclass(frozen=True)
class ProblemPathCandidateDecisionResult:
    candidate: ProblemPathCandidate
    applied_path_id: Optional[str]


async def decide_problem_path_candidate_action(
    db: AsyncSession,
    *,
    problem: Problem,
    candidate: ProblemPathCandidate,
    action: str,
) -> ProblemPathCandidateDecisionResult:
    normalized_action = str(action or "").strip().lower()
    applied_path_id: Optional[str] = None

    if normalized_action == "dismiss":
        candidate.status = "dismissed"
        candidate.selected_insertion = None
    elif normalized_action == "bookmark_for_later":
        candidate.status = "bookmarked"
        candidate.selected_insertion = "bookmark_for_later"
    elif normalized_action in {"insert_before_current_main", "save_as_side_branch"}:
        candidate.status = "planned"
        candidate.selected_insertion = _normalize_path_insertion(normalized_action)
        existing_branch_result = await db.execute(
            select(LearningPath).where(
                LearningPath.problem_id == str(problem.id),
                LearningPath.source_turn_id == candidate.source_turn_id,
                LearningPath.title == candidate.title,
                LearningPath.kind == _map_candidate_type_to_learning_path_kind(candidate.path_type),
            )
        )
        branch_path = existing_branch_result.scalar_one_or_none()

        if branch_path is None:
            if normalized_action == "insert_before_current_main":
                parent_path = await _load_main_learning_path(db, problem_id=str(problem.id))
                if not parent_path:
                    raise HTTPException(status_code=404, detail="Main learning path not found")
            else:
                parent_path = await _load_active_learning_path(db, problem_id=str(problem.id))
                if not parent_path:
                    raise HTTPException(status_code=404, detail="Active learning path not found")

            parent_step_index, parent_step_data = _resolve_current_step(parent_path)
            anchor_concept = (parent_step_data or {}).get("concept") or problem.title
            branch_path = LearningPath(
                problem_id=str(problem.id),
                title=candidate.title,
                kind=_map_candidate_type_to_learning_path_kind(candidate.path_type),
                parent_path_id=str(parent_path.id),
                source_turn_id=candidate.source_turn_id,
                return_step_id=parent_step_index,
                branch_reason=candidate.reason,
                is_active=True,
                path_data=_build_path_steps_from_candidate(candidate, anchor_concept=anchor_concept),
                current_step=0,
            )
            db.add(branch_path)
            await db.flush()

        await _set_active_learning_path(
            db=db,
            problem_id=str(problem.id),
            target_path_id=str(branch_path.id),
        )
        applied_path_id = str(branch_path.id)
    else:
        raise HTTPException(status_code=400, detail="Unsupported path candidate action")

    candidate.reviewed_at = datetime.utcnow()
    return ProblemPathCandidateDecisionResult(candidate=candidate, applied_path_id=applied_path_id)
