import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.services.llm_service import llm_service
from app.services.srs_service import srs_service
from app.services.cog_test_engine import CogTestEngine, get_engine, register_engine, unregister_engine
from app.api.routes.auth import get_current_user
from app.api.deps import get_current_user_from_query
from app.core.database import get_db
from app.models.entities.user import (
    User, CogTestSession, CogTestBlindSpot, CogTestSnapshot, ReviewSchedule
)

router = APIRouter(prefix="/cog-test", tags=["cognitive-test"])


class StartSessionBody(BaseModel):
    concept: str
    max_rounds: int = 3
    model_card_id: Optional[str] = None


async def _elevate_srs_priority_if_blind_spots(
    session: CogTestSession,
    db: AsyncSession,
) -> None:
    """If the session has blind spots and a linked model card, push that card
    to the front of the SRS review queue by applying quality=0."""
    # 1. Check for blind spots
    bs_result = await db.execute(
        select(CogTestBlindSpot)
        .where(CogTestBlindSpot.session_id == session.id)
        .limit(1)
    )
    if bs_result.scalars().first() is None:
        return  # no blind spots — leave SRS state unchanged

    # 2. Require a linked model card
    model_card_id = session.model_card_id
    if not model_card_id:
        return  # session started without model card link — skip silently

    # 3. Find existing ReviewSchedule
    sched_result = await db.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.user_id == session.user_id,
            ReviewSchedule.model_card_id == model_card_id,
        )
    )
    schedule = sched_result.scalars().first()

    # 4. Auto-create schedule if none exists
    if schedule is None:
        schedule = srs_service.schedule_card(model_card_id, session.user_id)
        db.add(schedule)
        await db.flush()

    # 5. Apply quality=0 — resets interval to 1 day, pushes card to front
    srs_service.process_review(schedule, quality=0)
    # Caller owns the transaction — do NOT commit here


# Used by GET /sessions/{id}/stream — see Phase 2 Plan 02-03
async def _stream_with_elevation(
    engine: CogTestEngine,
    session_id: str,
    db: AsyncSession,
):
    """Wrap engine.run() to trigger SRS elevation after natural session completion.

    Yields all SSE events from the engine, then — inside the generator's finally
    block — checks whether the session completed naturally and elevates SRS priority
    if blind spots exist.  Running inside the generator keeps the DB session alive
    within the EventSourceResponse lifecycle.
    """
    try:
        async for event in engine.run(db):
            yield event
    finally:
        # Post-stream: check if session completed naturally and elevate SRS
        try:
            session = await db.get(CogTestSession, session_id)
            if session and session.status == "completed":
                await _elevate_srs_priority_if_blind_spots(session, db)
                await db.commit()
        except Exception:
            pass  # best-effort — stop endpoint is the guaranteed fallback
        unregister_engine(session_id)


@router.post("/sessions")
async def create_session(
    body: StartSessionBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new cognitive test session, stopping any existing active session first."""
    import uuid

    # Stop any existing active session for this user
    existing_result = await db.execute(
        select(CogTestSession)
        .where(
            CogTestSession.user_id == str(current_user.id),
            CogTestSession.status == "active",
        )
        .limit(1)
    )
    existing = existing_result.scalars().first()
    if existing is not None:
        existing_engine = get_engine(existing.id)
        if existing_engine is not None:
            await existing_engine.stop()
        existing.status = "stopped"
        await db.commit()

    # Create new session
    new_id = str(uuid.uuid4())
    session = CogTestSession(
        id=new_id,
        user_id=str(current_user.id),
        concept=body.concept,
        model_card_id=body.model_card_id,
        max_rounds=body.max_rounds,
        status="active",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Instantiate and register engine
    engine = CogTestEngine(
        session_id=session.id,
        concept=session.concept,
        max_rounds=session.max_rounds,
    )
    register_engine(session.id, engine)

    return {"session_id": session.id, "concept": session.concept}


@router.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop an active session and elevate SRS priority if blind spots exist."""
    session = await db.get(CogTestSession, session_id)
    if not session or session.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    # Stop engine if running (engine may not exist if stream was never opened)
    engine = get_engine(session_id)
    if engine is not None:
        await engine.stop()

    # Update DB status regardless of engine state
    if session.status == "active":
        session.status = "stopped"
        await _elevate_srs_priority_if_blind_spots(session, db)
        await db.commit()

    return {"status": "stopped"}


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all sessions for the current user."""
    result = await db.execute(
        select(CogTestSession)
        .where(CogTestSession.user_id == str(current_user.id))
        .order_by(CogTestSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "concept": s.concept,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]


class SubmitTurnBody(BaseModel):
    text: str


@router.get("/sessions/{session_id}/stream")
async def stream_session(
    session_id: str,
    current_user: User = Depends(get_current_user_from_query),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream for a cognitive test session. Auth via ?token= query param."""
    session = await db.get(CogTestSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    engine = get_engine(session_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Session not active or engine not registered")

    return EventSourceResponse(_stream_with_elevation(engine, session_id, db))


@router.post("/sessions/{session_id}/turns")
async def submit_turn(
    session_id: str,
    body: SubmitTurnBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit user reply to unblock the engine for the next agent turn."""
    session = await db.get(CogTestSession, session_id)
    if not session or session.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    engine = get_engine(session_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Session not active or streaming")

    await engine.submit_user_turn(body.text)
    return {"status": "ok"}


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
