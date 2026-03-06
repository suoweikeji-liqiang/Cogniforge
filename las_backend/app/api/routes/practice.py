from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from uuid import UUID
from typing import List
import asyncio

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
    ReviewGenerateRequest,
    ReviewGenerateResponse,
    ReviewUpdate,
    ReviewResponse,
)
from app.api.routes.auth import get_current_user
from app.services.model_os_service import model_os_service
from app.services.review_service import review_service

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


router_reviews = APIRouter(prefix="/reviews", tags=["Reviews"])


def _build_review_markdown(review: Review) -> str:
    content = review.content or {}
    misconceptions = content.get("misconceptions", [])
    lines = [
        f"# {review.review_type.capitalize()} Review",
        "",
        f"**Period:** {review.period}",
        f"**Created At:** {review.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Summary",
        "",
        content.get("summary", "No summary."),
        "",
        "## Insights",
        "",
        content.get("insights", "No insights."),
        "",
        "## Next Steps",
        "",
        content.get("next_steps", "No next steps."),
        "",
        "## Misconceptions",
        "",
    ]

    if misconceptions:
        for item in misconceptions:
            lines.append(f"- {item}")
    else:
        lines.append("None recorded.")

    return "\n".join(lines)


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


@router_reviews.post("/generate", response_model=ReviewGenerateResponse)
async def generate_review(
    data: ReviewGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        content = await review_service.generate_review_content(
            db=db,
            user_id=str(current_user.id),
            review_type=data.review_type,
            period=data.period,
        )
        return {
            "review_type": data.review_type,
            "period": data.period,
            "content": content,
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=503, detail="Review generation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate review: {str(e)}")


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
    review_id_str = str(review_id)
    result = await db.execute(
        select(Review).where(
            Review.id == review_id_str,
            Review.user_id == current_user.id
        )
    )
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    return review


@router_reviews.get("/{review_id}/export")
async def export_review(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    review_id_str = str(review_id)
    result = await db.execute(
        select(Review).where(
            Review.id == review_id_str,
            Review.user_id == current_user.id
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    content = _build_review_markdown(review)
    filename = f"{review.review_type}-review-{review.period.replace(' ', '-')}.md"
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router_reviews.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: UUID,
    review_data: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    review_id_str = str(review_id)
    result = await db.execute(
        select(Review).where(Review.id == review_id_str, Review.user_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review_data.review_type is not None:
        review.review_type = review_data.review_type
    if review_data.period is not None:
        review.period = review_data.period
    if review_data.content is not None:
        review.content = review_data.content

    await db.commit()
    await db.refresh(review)
    return review


@router_reviews.delete("/{review_id}", status_code=204)
async def delete_review(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    review_id_str = str(review_id)
    result = await db.execute(
        select(Review).where(Review.id == review_id_str, Review.user_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    await db.delete(review)
    await db.commit()
    return None
