import re
from fastapi import APIRouter, Depends, HTTPException, Response
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.llm_service import llm_service
from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models.entities.user import (
    User, CogTestSession, CogTestBlindSpot, CogTestSnapshot
)

router = APIRouter(prefix="/cog-test", tags=["cognitive-test"])


@router.get("/stream-test")
async def stream_test(current_user=Depends(get_current_user)):
    async def event_generator():
        async for token in llm_service.stream_generate(
            messages=[{"role": "user", "content": "Say hello in 10 words"}],
            system_prompt="You are a helpful assistant.",
        ):
            yield {"event": "token", "data": token}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


@router.get("/sessions/{session_id}/report")
async def export_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(CogTestSession, session_id)
    if not session or session.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "active":
        raise HTTPException(status_code=400, detail="Session still active")

    blind_spots_result = await db.execute(
        select(CogTestBlindSpot)
        .where(CogTestBlindSpot.session_id == session_id)
        .order_by(CogTestBlindSpot.created_at)
    )
    blind_spots = list(blind_spots_result.scalars().all())

    snapshots_result = await db.execute(
        select(CogTestSnapshot)
        .where(CogTestSnapshot.session_id == session_id)
        .order_by(CogTestSnapshot.round_number.nullslast())
    )
    snapshots = list(snapshots_result.scalars().all())

    md = _build_report_markdown(session, blind_spots, snapshots)
    safe_name = re.sub(r'[^\w\-]', '', session.concept.replace(' ', '-'))[:50]
    filename = f"cog-report-{safe_name}.md"

    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_report_markdown(session, blind_spots, snapshots) -> str:
    lines = [
        "# Cognitive Diagnostic Report",
        "",
        f"**Concept:** {session.concept}",
        f"**Session ID:** {session.id}",
        f"**Status:** {session.status}",
        f"**Date:** {session.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
        "## Blind Spots",
        "",
    ]

    if blind_spots:
        for bs in blind_spots:
            lines.append(f"- **[{bs.category}]** {bs.description}")
    else:
        lines.append("No blind spots recorded.")

    lines += [
        "",
        "## Score Trajectory",
        "",
    ]

    if snapshots:
        for snap in snapshots:
            label = f"Round {snap.round_number}" if snap.round_number else "Final"
            lines.append(f"- {label}: {snap.understanding_score} (blind spots: {snap.blind_spot_count})")
    else:
        lines.append("No score data recorded.")

    lines += [
        "",
        "## Improvement Suggestions",
        "",
        "Based on the blind spots identified above, focus your review on:",
        "",
    ]

    gap_spots = [bs for bs in blind_spots if bs.category == "gap"]
    if gap_spots:
        for bs in gap_spots:
            lines.append(f"- {bs.description}")
    else:
        lines.append("- Continue reinforcing your understanding through spaced repetition.")

    return "\n".join(lines)
