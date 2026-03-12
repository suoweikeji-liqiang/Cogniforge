import re
from typing import List, Optional

from app.api.routes.problem_learning_path_support import _normalize_path_suggestion_type
from app.services.model_os_service import model_os_service


def _contains_cjk_text(*texts: Optional[str]) -> bool:
    return any(
        bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", str(text or "")))
        for text in texts
    )


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
    if answer_type == "comparison":
        extracted = _extract_comparison_targets_from_question(question)
        if extracted:
            return extracted

    mentioned = _find_question_concept_mentions(question, candidate_concepts)
    if answer_type == "comparison" and len(mentioned) >= 2:
        return model_os_service.normalize_concepts(mentioned[:2], limit=2)
    if answer_type != "comparison" and mentioned:
        return model_os_service.normalize_concepts(mentioned[:1], limit=1)
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


def _build_prerequisite_path_title(
    *,
    primary: str,
    prerequisite: str,
    cjk: bool,
) -> str:
    normalized_primary = _sanitize_question_concept_phrase(primary)
    normalized_prerequisite = _sanitize_question_concept_phrase(prerequisite)
    primary_key = model_os_service.normalize_concept_key(normalized_primary)
    prerequisite_key = model_os_service.normalize_concept_key(normalized_prerequisite)

    if normalized_prerequisite and prerequisite_key and prerequisite_key != primary_key:
        return normalized_prerequisite
    if cjk:
        return f"{normalized_primary or '当前主题'}前置基础"
    return f"Prerequisites for '{normalized_primary or 'the current topic'}'"


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
        prerequisite_title = _build_prerequisite_path_title(
            primary=primary,
            prerequisite=secondary,
            cjk=cjk,
        )
        suggestions.append(
            {
                "type": "prerequisite",
                "title": prerequisite_title,
                "reason": (
                    f"先补“{prerequisite_title}”，再回到“{primary}”。"
                    if cjk
                    else f"Study '{prerequisite_title}' first, then return to '{primary}'."
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
