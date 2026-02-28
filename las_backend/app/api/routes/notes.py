from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.models.entities.user import User, QuickNote
from app.schemas.quick_note import QuickNoteCreate, QuickNoteResponse
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/notes", tags=["Quick Notes"])


@router.post("/", response_model=QuickNoteResponse, status_code=201)
async def create_note(
    data: QuickNoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = QuickNote(
        user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(QuickNote)
        .where(QuickNote.user_id == current_user.id)
        .order_by(QuickNote.created_at.desc())
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
