"""Cognitive Challenge API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.entities.user import User, ModelCard, CognitiveChallenge
from app.api.routes.auth import get_current_user
from app.services.model_os_service import model_os_service

router = APIRouter(prefix="/challenges", tags=["Cognitive Challenges"])


@router.post("/generate")
async def generate_challenge(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a proactive cognitive challenge based on user's model cards."""
    uid = str(current_user.id)
    result = await db.execute(
        select(ModelCard).where(ModelCard.user_id == uid)
    )
    cards = list(result.scalars().all())
    if not cards:
        raise HTTPException(status_code=400, detail="No model cards to challenge")

    import random
    card = random.choice(cards)
    challenge_types = ["boundary_test", "cross_card", "socratic"]
    ctype = random.choice(challenge_types)

    prompts = {
        "boundary_test": f"Create a boundary-testing question for the concept '{card.title}'. "
            f"The question should challenge assumptions and test edge cases. "
            f"Context: {card.user_notes or ''}. Examples: {card.examples or []}",
        "cross_card": f"Create a cross-domain connection question about '{card.title}'. "
            f"Ask the user to explain how this concept relates to a different field.",
        "socratic": f"Create a Socratic question about '{card.title}' that guides the learner "
            f"to discover a deeper insight without giving the answer directly.",
    }

    question = await model_os_service.llm.generate(prompts[ctype])

    challenge = CognitiveChallenge(
        user_id=uid,
        model_card_id=card.id,
        challenge_type=ctype,
        question=question,
        context={"card_title": card.title},
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)

    return {
        "id": challenge.id,
        "challenge_type": ctype,
        "question": question,
        "card_title": card.title,
        "status": "pending",
    }


@router.get("/")
async def list_challenges(
    status: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List cognitive challenges for the current user."""
    query = select(CognitiveChallenge).where(
        CognitiveChallenge.user_id == str(current_user.id)
    )
    if status:
        query = query.where(CognitiveChallenge.status == status)
    query = query.order_by(CognitiveChallenge.created_at.desc())

    result = await db.execute(query)
    challenges = result.scalars().all()
    return [
        {
            "id": c.id,
            "challenge_type": c.challenge_type,
            "question": c.question,
            "card_title": (c.context or {}).get("card_title", ""),
            "status": c.status,
            "user_answer": c.user_answer,
            "ai_feedback": c.ai_feedback,
            "created_at": c.created_at.isoformat(),
        }
        for c in challenges
    ]


@router.post("/{challenge_id}/answer")
async def answer_challenge(
    challenge_id: str,
    answer: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit an answer to a cognitive challenge."""
    challenge = await db.get(CognitiveChallenge, challenge_id)
    if not challenge or challenge.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Challenge not found")

    feedback = await model_os_service.generate_feedback(
        user_response=answer,
        concept=(challenge.context or {}).get("card_title", ""),
        model_examples=[],
    )

    challenge.user_answer = answer
    challenge.ai_feedback = feedback
    challenge.status = "answered"
    await db.commit()

    return {
        "id": challenge.id,
        "ai_feedback": feedback,
        "status": "answered",
    }
