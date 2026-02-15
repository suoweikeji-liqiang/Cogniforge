from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.models.entities.user import (
    User,
    PracticeTask,
    PracticeSubmission,
    Review,
)
from app.schemas.practice import (
    PracticeTaskCreate,
    PracticeTaskResponse,
    PracticeSubmissionCreate,
    PracticeSubmissionResponse,
    ReviewCreate,
    ReviewResponse,
)
from app.api.routes.auth import get_current_user
from app.services.model_os_service import model_os_service

router = APIRouter(prefix="/practice", tags=["Practice"])


@router.post("/tasks", response_model=PracticeTaskResponse, status_code=201)
async def create_practice_task(
    task_data: PracticeTaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    db_task = PracticeTask(
        title=task_data.title,
        description=task_data.description,
        model_card_id=task_data.model_card_id,
        task_type=task_data.task_type,
    )
    
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    
    return db_task


@router.get("/tasks", response_model=List[PracticeTaskResponse])
async def list_practice_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PracticeTask)
        .order_by(PracticeTask.created_at.desc())
    )
    tasks = result.scalars().all()
    return tasks


@router.post("/submissions", response_model=PracticeSubmissionResponse, status_code=201)
async def create_submission(
    submission_data: PracticeSubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PracticeTask).where(PracticeTask.id == submission_data.practice_task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Practice task not found")
    
    feedback = await model_os_service.generate_feedback(
        user_response=submission_data.solution,
        concept=task.title,
        model_examples=[],
    )
    
    db_submission = PracticeSubmission(
        user_id=current_user.id,
        practice_task_id=submission_data.practice_task_id,
        solution=submission_data.solution,
        feedback=feedback,
    )
    
    db.add(db_submission)
    await db.commit()
    await db.refresh(db_submission)
    
    return db_submission


@router.get("/submissions", response_model=List[PracticeSubmissionResponse])
async def list_submissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PracticeSubmission)
        .where(PracticeSubmission.user_id == current_user.id)
        .order_by(PracticeSubmission.created_at.desc())
    )
    submissions = result.scalars().all()
    return submissions


router_reviews = APIRouter(prefix="/reviews", tags=["Reviews"])


@router_reviews.post("/", response_model=ReviewResponse, status_code=201)
async def create_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    db_review = Review(
        user_id=current_user.id,
        review_type=review_data.review_type,
        period=review_data.period,
        content=review_data.content,
    )
    
    db.add(db_review)
    await db.commit()
    await db.refresh(db_review)
    
    return db_review


@router_reviews.get("/", response_model=List[ReviewResponse])
async def list_reviews(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Review)
        .where(Review.user_id == current_user.id)
        .order_by(Review.created_at.desc())
    )
    reviews = result.scalars().all()
    return reviews


@router_reviews.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Review).where(
            Review.id == review_id,
            Review.user_id == current_user.id
        )
    )
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return review
