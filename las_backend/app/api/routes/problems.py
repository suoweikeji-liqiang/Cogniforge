from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.models.entities.user import User, Problem, LearningPath
from app.schemas.problem import (
    ProblemCreate,
    ProblemUpdate,
    ProblemResponse,
    ProblemResponseCreate,
    ProblemResponseResponse,
    LearningPathResponse,
)
from app.api.routes.auth import get_current_user
from app.services.model_os_service import model_os_service

router = APIRouter(prefix="/problems", tags=["Problems"])


@router.post("/", response_model=ProblemResponse, status_code=201)
async def create_problem(
    problem_data: ProblemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    db_problem = Problem(
        user_id=current_user.id,
        title=problem_data.title,
        description=problem_data.description,
        associated_concepts=problem_data.associated_concepts,
    )
    
    db.add(db_problem)
    await db.commit()
    await db.refresh(db_problem)
    
    existing_knowledge = []
    learning_path_data = await model_os_service.generate_learning_path(
        problem_title=problem_data.title,
        problem_description=problem_data.description or "",
        existing_knowledge=existing_knowledge,
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Problem)
        .where(Problem.user_id == current_user.id)
        .order_by(Problem.created_at.desc())
    )
    problems = result.scalars().all()
    return problems


@router.get("/{problem_id}", response_model=ProblemResponse)
async def get_problem(
    problem_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Problem).where(
            Problem.id == problem_id,
            Problem.user_id == current_user.id
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
            Problem.id == problem_id,
            Problem.user_id == current_user.id
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
            Problem.id == problem_id,
            Problem.user_id == current_user.id
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
            Problem.id == problem_id,
            Problem.user_id == current_user.id
        )
    )
    problem = result.scalar_one_or_none()
    
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    
    feedback = await model_os_service.generate_feedback(
        user_response=response_data.user_response,
        concept=problem.title,
        model_examples=problem.associated_concepts,
    )
    
    from app.models.entities.user import ProblemResponse as ProblemResponseModel
    db_response = ProblemResponseModel(
        problem_id=problem_id,
        user_response=response_data.user_response,
        system_feedback=feedback,
    )
    
    db.add(db_response)
    await db.commit()
    await db.refresh(db_response)
    
    return db_response


@router.get("/{problem_id}/learning-path", response_model=LearningPathResponse)
async def get_learning_path(
    problem_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(LearningPath).where(
            LearningPath.problem_id == problem_id,
        )
    )
    learning_path = result.scalar_one_or_none()
    
    if not learning_path:
        raise HTTPException(status_code=404, detail="Learning path not found")
    
    return learning_path
