import re
from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities.user import LearningPath, ProblemPathCandidate


def _contains_cjk_text(*texts: Optional[str]) -> bool:
    return any(
        bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", str(text or "")))
        for text in texts
    )


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


def _normalize_path_suggestion_type(
    raw_type: Optional[str],
    default: str = "branch_deep_dive",
) -> str:
    path_type = str(raw_type or default).strip().lower().replace(" ", "_")
    if path_type not in {"prerequisite", "branch_deep_dive", "comparison_path"}:
        return default
    return path_type


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
                    "Write side-by-side boundaries, tradeoffs, and decision cues."
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
