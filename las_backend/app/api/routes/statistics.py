"""Learning statistics API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import hashlib

from app.core.database import get_db
from app.models.entities.user import (
    User, Problem, ModelCard, Conversation,
    EvolutionLog, ReviewSchedule, Review, LearningPath,
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
    """Get knowledge graph data from model cards and problem learning paths."""
    uid = str(current_user.id)
    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()
    edge_ids: set[tuple[str, str, str]] = set()

    def add_node(
        node_id: str,
        label: str,
        node_type: str,
        route_id: str | None = None,
        version: int = 1,
        examples_count: int = 0,
    ):
        if node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "version": version,
                "examples_count": examples_count,
                "node_type": node_type,
                "route_id": route_id,
            }
        )

    def add_edge(source: str, target: str, label: str):
        if source not in node_ids or target not in node_ids:
            return
        key = (source, target, label)
        if key in edge_ids:
            return
        edge_ids.add(key)
        edges.append({"source": source, "target": target, "label": label})

    cards_result = await db.execute(select(ModelCard).where(ModelCard.user_id == uid))
    cards = cards_result.scalars().all()
    pending_parent_edges: list[tuple[str, str]] = []
    for card in cards:
        card_id = str(card.id)
        add_node(
            node_id=card_id,
            label=card.title,
            node_type="model_card",
            route_id=card_id,
            version=card.version or 1,
            examples_count=len(card.examples or []),
        )
        if card.parent_id:
            pending_parent_edges.append((str(card.parent_id), card_id))

        if card.concept_maps and isinstance(card.concept_maps, dict):
            map_node_index: dict[str, str] = {}
            for concept_node in card.concept_maps.get("nodes", []):
                if not isinstance(concept_node, dict):
                    continue
                concept_node_key = str(concept_node.get("id") or "").strip()
                if not concept_node_key:
                    continue
                concept_node_id = f"cardconcept:{card_id}:{concept_node_key}"
                map_node_index[concept_node_key] = concept_node_id
                add_node(
                    node_id=concept_node_id,
                    label=str(concept_node.get("label") or concept_node_key),
                    node_type="concept",
                )
                add_edge(card_id, concept_node_id, "contains")

            for concept_edge in card.concept_maps.get("edges", []):
                if not isinstance(concept_edge, dict):
                    continue
                source_key = str(concept_edge.get("source") or "").strip()
                target_key = str(concept_edge.get("target") or "").strip()
                source_node_id = map_node_index.get(source_key)
                target_node_id = map_node_index.get(target_key)
                if source_node_id and target_node_id:
                    add_edge(
                        source_node_id,
                        target_node_id,
                        str(concept_edge.get("label") or "related"),
                    )

    for parent_id, child_id in pending_parent_edges:
        add_edge(parent_id, child_id, "evolved_to")

    problems_result = await db.execute(
        select(Problem, LearningPath)
        .outerjoin(LearningPath, LearningPath.problem_id == Problem.id)
        .where(Problem.user_id == uid)
    )
    for problem, learning_path in problems_result.all():
        problem_node_id = f"problem:{problem.id}"
        add_node(
            node_id=problem_node_id,
            label=problem.title,
            node_type="problem",
            route_id=str(problem.id),
            examples_count=len(problem.associated_concepts or []),
        )

        for concept in problem.associated_concepts or []:
            concept_text = str(concept or "").strip()
            if not concept_text:
                continue
            concept_hash = hashlib.sha1(concept_text.casefold().encode("utf-8")).hexdigest()[:12]
            concept_node_id = f"concept:{concept_hash}"
            add_node(
                node_id=concept_node_id,
                label=concept_text,
                node_type="concept",
            )
            add_edge(problem_node_id, concept_node_id, "related")

        if not learning_path or not isinstance(learning_path.path_data, list):
            continue

        previous_step_node_id: str | None = None
        for index, step in enumerate(learning_path.path_data):
            if not isinstance(step, dict):
                continue
            step_concept = str(step.get("concept") or "").strip()
            if not step_concept:
                continue
            step_node_id = f"problemstep:{problem.id}:{index}"
            add_node(
                node_id=step_node_id,
                label=step_concept,
                node_type="learning_step",
                route_id=str(problem.id),
                version=index + 1,
                examples_count=len(step.get("resources") or []),
            )
            add_edge(problem_node_id, step_node_id, "step")
            if previous_step_node_id:
                add_edge(previous_step_node_id, step_node_id, "next")
            previous_step_node_id = step_node_id

    return {"nodes": nodes, "edges": edges}
