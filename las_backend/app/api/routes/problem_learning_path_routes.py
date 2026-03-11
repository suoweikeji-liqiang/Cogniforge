from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.api.routes.problem_learning_path_support import (
    _load_active_learning_path,
    _normalize_learning_path_kind,
    _resolve_current_step,
    _set_active_learning_path,
)
from app.core.database import get_db
from app.models.entities.user import LearningPath, Problem, User
from app.schemas.problem import LearningPathProgressUpdate, LearningPathResponse

router = APIRouter(tags=["Problems"])


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
