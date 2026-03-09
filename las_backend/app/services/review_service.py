import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities.user import (
    CognitiveChallenge,
    EvolutionLog,
    ModelCard,
    PracticeSubmission,
    Problem,
    ReviewSchedule,
)
from app.services.llm_service import llm_service


def _clean_json_str(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


class ReviewService:
    async def generate_review_content(
        self,
        db: AsyncSession,
        user_id: str,
        review_type: str,
        period: str,
    ) -> dict[str, Any]:
        problems_total = await db.scalar(
            select(func.count(Problem.id)).where(Problem.user_id == user_id)
        ) or 0
        problems_completed = await db.scalar(
            select(func.count(Problem.id)).where(
                Problem.user_id == user_id,
                Problem.status == "completed",
            )
        ) or 0
        model_cards_total = await db.scalar(
            select(func.count(ModelCard.id)).where(ModelCard.user_id == user_id)
        ) or 0
        scheduled_reviews = await db.scalar(
            select(func.count(ReviewSchedule.id)).where(
                ReviewSchedule.user_id == user_id
            )
        ) or 0
        due_reviews = await db.scalar(
            select(func.count(ReviewSchedule.id)).where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.next_review_at <= datetime.utcnow(),
            )
        ) or 0
        submissions_total = await db.scalar(
            select(func.count(PracticeSubmission.id)).where(
                PracticeSubmission.user_id == user_id
            )
        ) or 0
        challenges_answered = await db.scalar(
            select(func.count(CognitiveChallenge.id)).where(
                CognitiveChallenge.user_id == user_id,
                CognitiveChallenge.status == "answered",
            )
        ) or 0

        evolution_result = await db.execute(
            select(EvolutionLog.action_taken, EvolutionLog.reason_for_change)
            .where(EvolutionLog.user_id == user_id)
            .order_by(EvolutionLog.created_at.desc())
            .limit(5)
        )
        recent_evolution = [
            {
                "action": row[0],
                "reason": row[1],
            }
            for row in evolution_result.all()
        ]

        prompt = f"""You are generating a concise learning review for a user.

Review type: {review_type}
Period: {period}

User activity summary:
- Total problems: {problems_total}
- Completed problems: {problems_completed}
- Model cards: {model_cards_total}
- Scheduled review cards: {scheduled_reviews}
- Due spaced-repetition reviews: {due_reviews}
- Recent evolution actions: {json.dumps(recent_evolution, ensure_ascii=False)}
- Supporting activity:
  - Practice submissions: {submissions_total}
  - Answered cognitive challenges: {challenges_answered}

Return ONLY valid JSON in this exact format:
{{
  "summary": "2-3 sentence summary",
  "insights": "key insight about model-card quality, review rhythm, and learning progress",
  "next_steps": "concrete next actions tied to review, model-card refinement, or the next problem step",
  "misconceptions": ["misconception 1", "misconception 2"]
}}
"""

        response = await llm_service.generate(prompt)

        try:
            parsed = json.loads(_clean_json_str(response))
            if isinstance(parsed, dict):
                return {
                    "summary": parsed.get("summary", ""),
                    "insights": parsed.get("insights", ""),
                    "next_steps": parsed.get("next_steps", ""),
                    "misconceptions": parsed.get("misconceptions", []),
                }
        except json.JSONDecodeError:
            pass

        fallback_summary = (
            f"{review_type.capitalize()} review for {period}: "
            f"{problems_completed}/{problems_total} problems completed, "
            f"{model_cards_total} model cards, "
            f"{due_reviews} due reviews."
        )
        return {
            "summary": fallback_summary,
            "insights": "Learning activity is being recorded, but the review output was generated using fallback logic centered on model cards and review cadence.",
            "next_steps": "Complete pending review cards, refine the model cards that changed recently, and continue the next concrete problem step.",
            "misconceptions": [],
        }


review_service = ReviewService()
