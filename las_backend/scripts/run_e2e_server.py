import asyncio
import atexit
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

import uvicorn


_tmp_db = tempfile.NamedTemporaryFile(prefix="cogniforge-e2e-", suffix=".db", delete=False)
Path(_tmp_db.name).touch(exist_ok=True)

os.environ["DATABASE_FILE"] = _tmp_db.name
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["SECRET_KEY"] = "cogniforge-e2e-secret"
os.environ["PROBLEM_CONCEPT_AUTO_ACCEPT_CONFIDENCE"] = "1.0"
os.environ.setdefault("BACKEND_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")


def _cleanup() -> None:
    Path(_tmp_db.name).unlink(missing_ok=True)


atexit.register(_cleanup)

from app.main import app  # noqa: E402
from app.services.model_os_service import model_os_service  # noqa: E402


def _contains_cjk_text(*texts: Optional[str]) -> bool:
    for text in texts:
        if text and re.search(r"[\u4e00-\u9fff]", str(text)):
            return True
    return False


def _stream_chunks(response: str) -> list[str]:
    if " " in response:
        return [f"{token} " for token in response.split(" ")]
    return list(response)


def _has_pass_signal(user_response: str) -> bool:
    lowered = (user_response or "").casefold()
    return any(token in lowered for token in ("checkpoint", "second", "threshold")) or any(
        token in (user_response or "")
        for token in ("检查点", "第二", "第二步", "阈值", "下一步")
    )


def _normalized_seed(title: str, description: str, existing_knowledge: list[str]) -> list[str]:
    cjk = _contains_cjk_text(title, description, *existing_knowledge)
    seed_terms = ["精确率", "召回率"] if cjk else ["precision", "recall"]
    return model_os_service.normalize_concepts(
        [*existing_knowledge, title, description, *seed_terms],
        limit=8,
    )


async def fake_build_problem_concepts_resilient(
    problem_title: str,
    problem_description: Optional[str] = None,
    seed_concepts: Optional[list[str]] = None,
    max_concepts: int = 8,
):
    return _normalized_seed(problem_title, problem_description or "", seed_concepts or [])[:max_concepts]


async def fake_generate_learning_path(
    problem_title: str,
    problem_description: str,
    existing_knowledge: list[str],
    associated_concepts: Optional[list[str]] = None,
):
    cjk = _contains_cjk_text(problem_title, problem_description, *(existing_knowledge or []), *(associated_concepts or []))
    if cjk:
        return [
            {
                "step": 1,
                "concept": "精确率与召回率",
                "description": "先理解不平衡分类场景下精确率与召回率的取舍。",
                "resources": ["精确率", "召回率"],
            },
            {
                "step": 2,
                "concept": "阈值决策",
                "description": "再用阈值变化观察偏向精确率或偏向召回率时会发生什么。",
                "resources": ["精确率", "召回率", "决策阈值"],
            },
        ]
    return [
        {
            "step": 1,
            "concept": "Precision vs Recall",
            "description": "Understand the tradeoff between precision and recall on an imbalanced classifier.",
            "resources": ["precision", "recall"],
        },
        {
            "step": 2,
            "concept": "Threshold decisions",
            "description": "Use decision thresholds to move between precision-heavy and recall-heavy behavior.",
            "resources": ["precision", "recall", "decision threshold"],
        },
    ]


async def fake_generate_learning_path_resilient(
    problem_title: str,
    problem_description: Optional[str] = None,
    existing_knowledge: Optional[list[str]] = None,
    associated_concepts: Optional[list[str]] = None,
    timeout_seconds: Optional[int] = None,
    **_: object,
):
    return await fake_generate_learning_path(
        problem_title,
        problem_description or "",
        existing_knowledge or [],
        associated_concepts or [],
    )


async def fake_generate_socratic_question(
    problem_title: str,
    problem_description: str,
    step_concept: str,
    step_description: str,
    question_kind: str,
    recent_responses: list[str],
    latest_feedback: Optional[dict] = None,
):
    cjk = _contains_cjk_text(problem_title, problem_description, step_concept, step_description, *(recent_responses or []))
    if cjk:
        if question_kind == "checkpoint":
            return f"如果要为了“{step_concept}”调整阈值，什么取舍会让你改选另一个阈值？"
        return f"请用一个具体场景解释“{step_concept}”里的核心取舍。"
    if question_kind == "checkpoint":
        return f"What tradeoff would make you choose a different threshold for '{step_concept}'?"
    return f"Explain the core tradeoff inside '{step_concept}' in one concrete scenario."


async def fake_stream_socratic_question(
    problem_title: str,
    problem_description: str,
    step_concept: str,
    step_description: str,
    question_kind: str,
    recent_responses: list[str],
    latest_feedback: Optional[dict] = None,
):
    response = await fake_generate_socratic_question(
        problem_title=problem_title,
        problem_description=problem_description,
        step_concept=step_concept,
        step_description=step_description,
        question_kind=question_kind,
        recent_responses=recent_responses,
        latest_feedback=latest_feedback,
    )
    for token in _stream_chunks(response):
        await asyncio.sleep(0.05)
        yield token


async def fake_generate_feedback_structured(
    user_response: str,
    concept: str,
    model_examples: list[str],
    retrieval_context: Optional[str] = None,
):
    await asyncio.sleep(0.08)
    cjk = _contains_cjk_text(user_response, concept, retrieval_context)
    if _has_pass_signal(user_response):
        return {
            "correctness": "correct",
            "misconceptions": [],
            "suggestions": (
                ["进入下一步，并继续用边界案例检验这个判断。"]
                if cjk
                else ["Move to the next step and stress-test the decision boundary."]
            ),
            "next_question": (
                f"现在围绕“{concept}”，哪一个指标取舍最关键？"
                if cjk
                else f"What metric tradeoff matters most for '{concept}' now?"
            ),
            "mastery_score": 88,
            "dimension_scores": {"concept": 88, "application": 84},
            "confidence": 0.91,
            "pass_stage": True,
        }
    return {
        "correctness": "mostly correct",
        "misconceptions": (
            ["需要把阈值带来的取舍说得更明确。"]
            if cjk
            else ["State the threshold tradeoff more explicitly."]
        ),
        "suggestions": (
            ["对比一个偏精确率的选择和一个偏召回率的选择。"]
            if cjk
            else ["Contrast one precision-heavy choice with one recall-heavy choice."]
        ),
        "next_question": (
            f"围绕“{concept}”，什么边界案例会改变你的选择？"
            if cjk
            else f"What boundary case would change your choice for '{concept}'?"
        ),
        "mastery_score": 62,
        "dimension_scores": {"concept": 62, "application": 58},
        "confidence": 0.74,
        "pass_stage": False,
    }


async def fake_extract_related_concepts_resilient(
    problem_title: str,
    problem_description: str,
    limit: int = 5,
):
    text = f"{problem_title}\n{problem_description}".casefold()
    cjk = _contains_cjk_text(problem_title, problem_description)
    candidates = []
    if "precision" in text or "精确率" in text:
        if cjk:
            candidates.extend(["精确率", "误报", "决策阈值"])
        else:
            candidates.extend(["precision", "false positives", "decision threshold"])
    if "recall" in text or "召回率" in text:
        if cjk:
            candidates.extend(["召回率", "漏报"])
        else:
            candidates.extend(["recall", "false negatives"])
    if "difference between" in text or "compare" in text or "区别" in text or "对比" in text:
        if cjk:
            candidates.extend(["对比基线", "取舍"])
        else:
            candidates.extend(["comparison baseline", "tradeoff"])
    if not candidates:
        candidates.extend([problem_title, "核心概念" if cjk else "core concept"])
    return model_os_service.normalize_concepts(candidates, limit=limit)


async def fake_generate(prompt: str, provider_type: Optional[str] = None, model_id: Optional[str] = None, **kwargs):
    if _contains_cjk_text(prompt):
        return "这是一个确定性的中文 E2E 响应。"
    return "Deterministic E2E response."


async def fake_generate_with_context(
    prompt: str,
    context: list[dict],
    retrieval_context: Optional[str] = None,
    provider_type: Optional[str] = None,
    model_id: Optional[str] = None,
    **kwargs,
):
    question = str(context[-1]["content"] if context else "").strip()
    cjk = _contains_cjk_text(question, retrieval_context, prompt)
    question_lower = question.casefold()
    if "threshold moves" in question_lower or "阈值" in question:
        if cjk:
            return (
                "当阈值提高时，误报通常会减少，但漏报可能会上升。"
                "先抓住这个取舍，再去比较精确率与召回率。"
            )
        return (
            "When the threshold moves, false negatives usually drop while false positives rise. "
            "Use that tradeoff as the first evidence anchor before comparing precision and recall."
        )
    if "difference between" in question_lower or "compare" in question_lower or "区别" in question or "差别" in question or "对比" in question:
        if cjk:
            return (
                "精确率关注预测为正的结果里有多少是真的。"
                "召回率关注实际为正的对象里你找回了多少。"
                "例如阈值更严格时，精确率常常上升，而召回率可能下降。"
            )
        return (
            "Precision measures how many predicted positives are correct. "
            "Recall measures how many actual positives you recover. "
            "Example: a stricter threshold usually raises precision and lowers recall."
        )
    if cjk:
        return "先从当前步骤概念出发，简要定义它，再用一个具体例子验证它。"
    return "Start from the current step concept, define it briefly, and test it with one concrete example."


async def fake_stream_generate_with_context(
    prompt: str,
    context: list[dict],
    retrieval_context: Optional[str] = None,
    provider_type: Optional[str] = None,
    model_id: Optional[str] = None,
    temperature: float = 0.7,
):
    response = await fake_generate_with_context(
        prompt=prompt,
        context=context,
        retrieval_context=retrieval_context,
        provider_type=provider_type,
        model_id=model_id,
    )
    for token in _stream_chunks(response):
        await asyncio.sleep(0.03)
        yield token


model_os_service.build_problem_concepts_resilient = fake_build_problem_concepts_resilient
model_os_service.generate_learning_path = fake_generate_learning_path
model_os_service.generate_learning_path_resilient = fake_generate_learning_path_resilient
model_os_service.generate_socratic_question = fake_generate_socratic_question
model_os_service.stream_socratic_question = fake_stream_socratic_question
model_os_service.generate_feedback_structured = fake_generate_feedback_structured
model_os_service.extract_related_concepts_resilient = fake_extract_related_concepts_resilient
model_os_service.llm.generate = fake_generate
model_os_service.llm.generate_with_context = fake_generate_with_context
model_os_service.generate_with_context = fake_generate_with_context
model_os_service.stream_generate_with_context = fake_stream_generate_with_context


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")
