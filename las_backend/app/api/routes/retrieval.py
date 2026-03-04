from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models.entities.user import RetrievalEvent, User
from app.schemas.retrieval import RetrievalEventResponse, RetrievalSummaryResponse


router = APIRouter(prefix="/retrieval", tags=["Retrieval"])


@router.get("/logs", response_model=list[RetrievalEventResponse])
async def list_retrieval_logs(
    source: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(RetrievalEvent)
        .where(RetrievalEvent.user_id == str(current_user.id))
        .order_by(RetrievalEvent.created_at.desc())
        .limit(limit)
    )
    if source:
        query = query.where(RetrievalEvent.source == source)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/summary", response_model=RetrievalSummaryResponse)
async def get_retrieval_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = str(current_user.id)

    totals = await db.execute(
        select(
            func.count(RetrievalEvent.id),
            func.coalesce(func.sum(RetrievalEvent.result_count), 0),
        ).where(RetrievalEvent.user_id == user_id)
    )
    total_events, total_hits = totals.one()

    source_rows = await db.execute(
        select(RetrievalEvent.source, func.count(RetrievalEvent.id))
        .where(RetrievalEvent.user_id == user_id)
        .group_by(RetrievalEvent.source)
    )
    source_breakdown = {source: count for source, count in source_rows.all()}

    average_hits = round((total_hits / total_events), 2) if total_events else 0.0
    zero_hit_events = await db.scalar(
        select(func.count(RetrievalEvent.id)).where(
            RetrievalEvent.user_id == user_id,
            RetrievalEvent.result_count == 0,
        )
    )
    poor_hit_events = await db.scalar(
        select(func.count(RetrievalEvent.id)).where(
            RetrievalEvent.user_id == user_id,
            RetrievalEvent.result_count <= 1,
        )
    )
    zero_hit_rate = round((zero_hit_events / total_events), 2) if total_events else 0.0
    health_status = "needs_attention" if zero_hit_events or average_hits < 1.5 else "healthy"

    return {
        "total_events": total_events or 0,
        "total_hits": total_hits or 0,
        "average_hits": average_hits,
        "zero_hit_events": zero_hit_events or 0,
        "poor_hit_events": poor_hit_events or 0,
        "zero_hit_rate": zero_hit_rate,
        "health_status": health_status,
        "source_breakdown": source_breakdown,
    }
