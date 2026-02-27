"""Spaced Repetition Service using SM-2 algorithm."""
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entities.user import ReviewSchedule, ModelCard


class SRSService:
    """SM-2 algorithm implementation for spaced repetition."""

    def schedule_card(self, card_id: str, user_id: str) -> ReviewSchedule:
        """Create initial review schedule for a model card."""
        return ReviewSchedule(
            user_id=user_id,
            model_card_id=card_id,
            ease_factor=2500,
            interval_days=1,
            repetitions=0,
            next_review_at=datetime.utcnow() + timedelta(days=1),
        )

    def process_review(
        self, schedule: ReviewSchedule, quality: int
    ) -> ReviewSchedule:
        """
        Process a review using SM-2 algorithm.
        quality: 0-5 (0=forgot, 5=perfect recall)
        """
        quality = max(0, min(5, quality))
        ef = schedule.ease_factor / 1000.0

        if quality >= 3:
            if schedule.repetitions == 0:
                interval = 1
            elif schedule.repetitions == 1:
                interval = 6
            else:
                interval = round(schedule.interval_days * ef)
            schedule.repetitions += 1
        else:
            schedule.repetitions = 0
            interval = 1

        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ef = max(1.3, ef)

        schedule.ease_factor = round(ef * 1000)
        schedule.interval_days = interval
        schedule.last_reviewed_at = datetime.utcnow()
        schedule.next_review_at = datetime.utcnow() + timedelta(days=interval)
        return schedule

    async def get_due_cards(
        self, db: AsyncSession, user_id: str
    ) -> list:
        """Get all model cards due for review."""
        result = await db.execute(
            select(ReviewSchedule)
            .where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.next_review_at <= datetime.utcnow(),
            )
            .order_by(ReviewSchedule.next_review_at.asc())
        )
        return list(result.scalars().all())

    async def get_all_schedules(
        self, db: AsyncSession, user_id: str
    ) -> list:
        """Get all review schedules for a user."""
        result = await db.execute(
            select(ReviewSchedule)
            .where(ReviewSchedule.user_id == user_id)
            .order_by(ReviewSchedule.next_review_at.asc())
        )
        return list(result.scalars().all())


srs_service = SRSService()
