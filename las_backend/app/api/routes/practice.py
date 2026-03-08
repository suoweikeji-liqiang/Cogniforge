from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.entities.user import (
    User,
    PracticeTask,
    PracticeSubmission,
)
from app.schemas.practice import (
    PracticeTaskCreate,
    PracticeTaskResponse,
    PracticeSubmissionCreate,
    PracticeSubmissionResponse,
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
        user_id=current_user.id,
        title=task_data.title,
        description=task_data.description,
        model_card_id=str(task_data.model_card_id) if task_data.model_card_id else None,
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
        .where(PracticeTask.user_id == current_user.id)
        .order_by(PracticeTask.created_at.desc())
    )
    tasks = result.scalars().all()
    return tasks


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_practice_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    task_id_str = str(task_id)
    result = await db.execute(
        select(PracticeTask).where(
            PracticeTask.id == task_id_str,
            PracticeTask.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Practice task not found")

    await db.execute(
        delete(PracticeSubmission).where(PracticeSubmission.practice_task_id == task_id_str)
    )
    await db.delete(task)
    await db.commit()
    return None


@router.post("/submissions", response_model=PracticeSubmissionResponse, status_code=201)
async def create_submission(
    submission_data: PracticeSubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    practice_task_id = str(submission_data.practice_task_id)
    result = await db.execute(
        select(PracticeTask).where(PracticeTask.id == practice_task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Practice task not found")

    retrieval_context = await model_os_service.build_retrieval_context(
        db=db,
        user_id=str(current_user.id),
        query=f"{task.title}\n{submission_data.solution}",
        source="practice_submission",
    )
    structured_feedback = await model_os_service.generate_feedback_structured(
        user_response=submission_data.solution,
        concept=task.title,
        model_examples=[],
        retrieval_context=retrieval_context,
    )
    feedback = model_os_service.format_feedback_text(structured_feedback)
    
    db_submission = PracticeSubmission(
        user_id=current_user.id,
        practice_task_id=practice_task_id,
        solution=submission_data.solution,
        feedback=feedback,
    )
    
    db.add(db_submission)
    await db.commit()
    await db.refresh(db_submission)
    
    return {
        "id": db_submission.id,
        "user_id": db_submission.user_id,
        "practice_task_id": db_submission.practice_task_id,
        "solution": db_submission.solution,
        "feedback": db_submission.feedback,
        "structured_feedback": structured_feedback,
        "created_at": db_submission.created_at,
    }


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
    submissions = []
    for submission in result.scalars().all():
        submissions.append({
            "id": submission.id,
            "user_id": submission.user_id,
            "practice_task_id": submission.practice_task_id,
            "solution": submission.solution,
            "feedback": submission.feedback,
            "structured_feedback": model_os_service.parse_feedback_text(submission.feedback),
            "created_at": submission.created_at,
        })
    return submissions


@router.get("/submissions/{submission_id}", response_model=PracticeSubmissionResponse)
async def get_submission(
    submission_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    submission_id_str = str(submission_id)
    result = await db.execute(
        select(PracticeSubmission).where(
            PracticeSubmission.id == submission_id_str,
            PracticeSubmission.user_id == current_user.id
        )
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {
        "id": submission.id,
        "user_id": submission.user_id,
        "practice_task_id": submission.practice_task_id,
        "solution": submission.solution,
        "feedback": submission.feedback,
        "structured_feedback": model_os_service.parse_feedback_text(submission.feedback),
        "created_at": submission.created_at,
    }
