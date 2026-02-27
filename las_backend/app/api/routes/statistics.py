"""Learning statistics API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.entities.user import (
    User, Problem, ModelCard, Conversation,
    EvolutionLog, ReviewSchedule, Review,
)
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/statistics", tags=["Statistics"])


@router.get("/overview")
async def get_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get learning overview statistics."""
    uid = str(current_user.id)

    problems_count = await db.scalar(
        select(func.count(Problem.id)).where(Problem.user_id == uid)
    )
    cards_count = await db.scalar(
        select(func.count(ModelCard.id)).where(ModelCard.user_id == uid)
    )
    convs_count = await db.scalar(
        select(func.count(Conversation.id)).where(Conversation.user_id == uid)
    )
    reviews_count = await db.scalar(
        select(func.count(Review.id)).where(Review.user_id == uid)
    )

    # Due reviews count
    due_count = await db.scalar(
        select(func.count(ReviewSchedule.id)).where(
            ReviewSchedule.user_id == uid,
            ReviewSchedule.next_review_at <= datetime.utcnow(),
        )
    )

    return {
        "problems": problems_count or 0,
        "model_cards": cards_count or 0,
        "conversations": convs_count or 0,
        "reviews": reviews_count or 0,
        "due_reviews": due_count or 0,
    }


@router.get("/heatmap")
async def get_heatmap(
    days: int = 90,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get learning activity heatmap data (like GitHub contributions)."""
    uid = str(current_user.id)
    since = datetime.utcnow() - timedelta(days=days)

    # Count activities per day from evolution logs
    logs = await db.execute(
        select(EvolutionLog.created_at)
        .where(EvolutionLog.user_id == uid, EvolutionLog.created_at >= since)
    )
    # Count model card creations
    cards = await db.execute(
        select(ModelCard.created_at)
        .where(ModelCard.user_id == uid, ModelCard.created_at >= since)
    )
    # Count conversations
    convs = await db.execute(
        select(Conversation.created_at)
        .where(Conversation.user_id == uid, Conversation.created_at >= since)
    )

    activity = {}
    for row in logs.all():
        day = row[0].strftime("%Y-%m-%d")
        activity[day] = activity.get(day, 0) + 1
    for row in cards.all():
        day = row[0].strftime("%Y-%m-%d")
        activity[day] = activity.get(day, 0) + 2
    for row in convs.all():
        day = row[0].strftime("%Y-%m-%d")
        activity[day] = activity.get(day, 0) + 1

    return {"days": days, "activity": activity}


@router.get("/knowledge-graph")
async def get_knowledge_graph(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get knowledge graph data from all model cards."""
    uid = str(current_user.id)
    result = await db.execute(
        select(ModelCard).where(ModelCard.user_id == uid)
    )
    cards = result.scalars().all()

    nodes = []
    edges = []
    for card in cards:
        nodes.append({
            "id": card.id,
            "label": card.title,
            "version": card.version,
            "examples_count": len(card.examples or []),
        })
        # Extract edges from concept_maps if available
        if card.concept_maps and isinstance(card.concept_maps, dict):
            for edge in card.concept_maps.get("edges", []):
                edges.append({
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "label": edge.get("label", ""),
                    "card_id": card.id,
                })
        # Link to parent if exists
        if card.parent_id:
            edges.append({
                "source": card.parent_id,
                "target": card.id,
                "label": "evolved_to",
            })

    return {"nodes": nodes, "edges": edges}
