import asyncio
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models.entities.user import Review, User
from app.schemas.review import (
    ReviewCreate,
    ReviewGenerateRequest,
    ReviewGenerateResponse,
    ReviewResponse,
    ReviewUpdate,
)
from app.services.review_service import review_service

router = APIRouter(prefix="/reviews", tags=["Reviews"])


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


@router.post("/", response_model=ReviewResponse, status_code=201)
async def create_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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


@router.post("/generate", response_model=ReviewGenerateResponse)
async def generate_review(
    data: ReviewGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate review: {str(exc)}")


@router.get("/", response_model=List[ReviewResponse])
async def list_reviews(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review)
        .where(Review.user_id == current_user.id)
        .order_by(Review.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review).where(
            Review.id == str(review_id),
            Review.user_id == current_user.id,
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.get("/{review_id}/export")
async def export_review(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review).where(
            Review.id == str(review_id),
            Review.user_id == current_user.id,
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


@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: UUID,
    review_data: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review).where(
            Review.id == str(review_id),
            Review.user_id == current_user.id,
        )
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


@router.delete("/{review_id}", status_code=204)
async def delete_review(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review).where(
            Review.id == str(review_id),
            Review.user_id == current_user.id,
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    await db.delete(review)
    await db.commit()
    return None
