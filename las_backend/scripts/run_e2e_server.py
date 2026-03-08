import atexit
import os
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


def _normalized_seed(title: str, description: str, existing_knowledge: list[str]) -> list[str]:
    return model_os_service.normalize_concepts(
        [*existing_knowledge, title, description, "precision", "recall"],
        limit=8,
    )


async def fake_build_problem_concepts_resilient(
    problem_title: str,
    problem_description: Optional[str] = None,
    seed_concepts: Optional[list[str]] = None,
    max_concepts: int = 8,
):
    return _normalized_seed(problem_title, problem_description or "", seed_concepts or [])[:max_concepts]


async def fake_generate_learning_path(problem_title: str, problem_description: str, existing_knowledge: list[str]):
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
    timeout_seconds: Optional[int] = None,
    **_: object,
):
    return await fake_generate_learning_path(problem_title, problem_description or "", existing_knowledge or [])


async def fake_generate_socratic_question(
    problem_title: str,
    problem_description: str,
    step_concept: str,
    step_description: str,
    question_kind: str,
    recent_responses: list[str],
    latest_feedback: Optional[dict] = None,
):
    if question_kind == "checkpoint":
        return f"What tradeoff would make you choose a different threshold for '{step_concept}'?"
    return f"Explain the core tradeoff inside '{step_concept}' in one concrete scenario."


async def fake_generate_feedback_structured(
    user_response: str,
    concept: str,
    model_examples: list[str],
    retrieval_context: Optional[str] = None,
):
    lowered = (user_response or "").casefold()
    if "checkpoint" in lowered or "second" in lowered or "threshold" in lowered:
        return {
            "correctness": "correct",
            "misconceptions": [],
            "suggestions": ["Move to the next step and stress-test the decision boundary."],
            "next_question": f"What metric tradeoff matters most for '{concept}' now?",
            "mastery_score": 88,
            "dimension_scores": {"concept": 88, "application": 84},
            "confidence": 0.91,
            "pass_stage": True,
        }
    return {
        "correctness": "mostly correct",
        "misconceptions": ["State the threshold tradeoff more explicitly."],
        "suggestions": ["Contrast one precision-heavy choice with one recall-heavy choice."],
        "next_question": f"What boundary case would change your choice for '{concept}'?",
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
    candidates = []
    if "precision" in text:
        candidates.extend(["precision", "false positives", "decision threshold"])
    if "recall" in text:
        candidates.extend(["recall", "false negatives"])
    if "difference between" in text or "compare" in text:
        candidates.extend(["comparison baseline", "tradeoff"])
    if not candidates:
        candidates.extend([problem_title, "core concept"])
    return model_os_service.normalize_concepts(candidates, limit=limit)


async def fake_generate(prompt: str, provider_type: Optional[str] = None, model_id: Optional[str] = None, **kwargs):
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
    if "difference between" in question.casefold():
        return (
            "Precision measures how many predicted positives are correct. "
            "Recall measures how many actual positives you recover. "
            "Example: a stricter threshold usually raises precision and lowers recall."
        )
    return (
        "Start from the current step concept, define it briefly, and test it with one concrete example."
    )


model_os_service.build_problem_concepts_resilient = fake_build_problem_concepts_resilient
model_os_service.generate_learning_path = fake_generate_learning_path
model_os_service.generate_learning_path_resilient = fake_generate_learning_path_resilient
model_os_service.generate_socratic_question = fake_generate_socratic_question
model_os_service.generate_feedback_structured = fake_generate_feedback_structured
model_os_service.extract_related_concepts_resilient = fake_extract_related_concepts_resilient
model_os_service.llm.generate = fake_generate
model_os_service.llm.generate_with_context = fake_generate_with_context
model_os_service.generate_with_context = fake_generate_with_context


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")
