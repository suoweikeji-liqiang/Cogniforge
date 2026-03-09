from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.models.entities.user import User, Problem, ProblemTurn, QuickNote
from app.schemas.quick_note import QuickNoteCreate, QuickNoteResponse
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/notes", tags=["Quick Notes"])


@router.post("/", response_model=QuickNoteResponse, status_code=201)
async def create_note(
    data: QuickNoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    problem_id = str(data.problem_id) if data.problem_id else None
    source_turn_id = str(data.source_turn_id) if data.source_turn_id else None

    if problem_id:
        problem_result = await db.execute(
            select(Problem).where(
                Problem.id == problem_id,
                Problem.user_id == str(current_user.id),
            )
        )
        if problem_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Problem not found")

    if source_turn_id:
        turn_result = await db.execute(
            select(ProblemTurn).where(
                ProblemTurn.id == source_turn_id,
                ProblemTurn.user_id == str(current_user.id),
            )
        )
        turn = turn_result.scalar_one_or_none()
        if turn is None:
            raise HTTPException(status_code=404, detail="Source turn not found")
        if problem_id and str(turn.problem_id) != problem_id:
            raise HTTPException(status_code=400, detail="Source turn must belong to the same problem")
        problem_id = problem_id or str(turn.problem_id)

    note = QuickNote(
        user_id=current_user.id,
        problem_id=problem_id,
        source_turn_id=source_turn_id,
        content=data.content,
        source=data.source,
        tags=data.tags,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.get("/", response_model=List[QuickNoteResponse])
async def list_notes(
    problem_id: UUID | None = Query(default=None),
    source_turn_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = [QuickNote.user_id == current_user.id]
    if problem_id:
        filters.append(QuickNote.problem_id == str(problem_id))
    if source_turn_id:
        filters.append(QuickNote.source_turn_id == str(source_turn_id))

    result = await db.execute(
        select(QuickNote).where(*filters).order_by(QuickNote.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(QuickNote).where(
            QuickNote.id == str(note_id),
            QuickNote.user_id == current_user.id,
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    await db.commit()
