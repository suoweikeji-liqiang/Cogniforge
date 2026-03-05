from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, desc
from uuid import UUID
from typing import List, Optional

from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities.user import User, Problem, LearningPath
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
            Problem.user_id == str(current_user.id)
        )
    )
    problem = result.scalar_one_or_none()
    
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    learning_path_result = await db.execute(
        select(LearningPath).where(LearningPath.problem_id == str(problem_id))
    )
    learning_path = learning_path_result.scalar_one_or_none()
    current_step_index, current_step_data = _resolve_current_step(learning_path)

    step_concept = (
        (current_step_data or {}).get("concept")
        or problem.title
    )
    step_description = (current_step_data or {}).get("description") or ""
    step_resources = (current_step_data or {}).get("resources") or []
    model_examples = model_os_service.normalize_concepts(
        [step_concept, *(problem.associated_concepts or []), *step_resources],
        limit=10,
    )

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
    structured_feedback = await model_os_service.generate_feedback_structured(
        user_response=response_data.user_response,
        concept=step_concept,
        model_examples=model_examples,
        retrieval_context=retrieval_context,
    )
    feedback = model_os_service.format_feedback_text(structured_feedback)
    max_concepts = max(6, int(settings.PROBLEM_MAX_ASSOCIATED_CONCEPTS))
    existing_concepts = model_os_service.normalize_concepts(
        problem.associated_concepts or [],
        limit=max_concepts,
    )
    misconceptions = [str(item).strip() for item in (structured_feedback.get("misconceptions") or []) if str(item).strip()]
    suggestions = [str(item).strip() for item in (structured_feedback.get("suggestions") or []) if str(item).strip()]
    next_question = str(structured_feedback.get("next_question") or "").strip()

    concept_context_parts = [
        f"User response:\n{response_data.user_response}",
        f"Current step concept:\n{step_concept}",
        f"Current step description:\n{step_description}",
    ]
    if misconceptions:
        concept_context_parts.append("Misconceptions:\n" + "\n".join(f"- {item}" for item in misconceptions))
    if suggestions:
        concept_context_parts.append("Suggestions:\n" + "\n".join(f"- {item}" for item in suggestions))
    if next_question:
        concept_context_parts.append(f"Next question:\n{next_question}")

    inferred_concepts = await model_os_service.extract_related_concepts_resilient(
        problem_title=problem.title,
        problem_description="\n\n".join(concept_context_parts),
        limit=min(max_concepts, 10),
    )
    merged_concepts = model_os_service.normalize_concepts(
        existing_concepts + inferred_concepts + [step_concept],
        limit=max_concepts,
    )
    existing_keys = {item.casefold() for item in existing_concepts}
    new_concepts = [
        concept
        for concept in merged_concepts
        if concept.casefold() not in existing_keys
    ]
    concepts_updated = bool(new_concepts)
    if concepts_updated:
        problem.associated_concepts = merged_concepts
        model_os_service.refresh_problem_embedding(problem)

    auto_advanced = False
    new_current_step = learning_path.current_step if learning_path else None

    if learning_path and _should_auto_advance(structured_feedback, settings.PROBLEM_AUTO_ADVANCE_MODE):
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
    
    from app.models.entities.user import ProblemResponse as ProblemResponseModel
    db_response = ProblemResponseModel(
        problem_id=str(problem_id),
        user_response=response_data.user_response,
        system_feedback=feedback,
    )
    
    db.add(db_response)
    await db.commit()
    await db.refresh(db_response)
    
    return {
        "id": db_response.id,
        "problem_id": db_response.problem_id,
        "user_response": db_response.user_response,
        "system_feedback": db_response.system_feedback,
        "structured_feedback": structured_feedback,
        "auto_advanced": auto_advanced,
        "new_current_step": new_current_step,
        "new_concepts": new_concepts,
        "concepts_updated": concepts_updated,
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

    from app.models.entities.user import ProblemResponse as ProblemResponseModel

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
            "user_response": response.user_response,
            "system_feedback": response.system_feedback,
            "structured_feedback": model_os_service.parse_feedback_text(response.system_feedback),
            "created_at": response.created_at,
        })
    return responses


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

    from app.models.entities.user import ProblemResponse as ProblemResponseModel

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

    path_result = await db.execute(
        select(LearningPath).where(LearningPath.problem_id == str(problem_id))
    )
    learning_path = path_result.scalar_one_or_none()
    step_index, step_data = _resolve_current_step(learning_path)
    step_concept = (step_data or {}).get("concept") or problem.title
    step_description = (step_data or {}).get("description") or (problem.description or "")
    mode = _normalize_answer_mode(payload.answer_mode)

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

    answer = await model_os_service.generate_with_context(
        prompt=prompt,
        context=[{"role": "user", "content": payload.question}],
        retrieval_context=retrieval_context,
    )

    return {
        "question": payload.question,
        "answer": answer,
        "answer_mode": mode,
        "step_index": step_index,
        "step_concept": step_concept,
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
