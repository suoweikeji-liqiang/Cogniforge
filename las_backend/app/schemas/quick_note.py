from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class QuickNoteCreate(BaseModel):
    content: str
    source: str = "text"
    tags: List[str] = []


class QuickNoteResponse(BaseModel):
    id: UUID
    user_id: UUID
    content: str
    source: str
    tags: List[str]
    created_at: datetime

    class Config:
        from_attributes = True
