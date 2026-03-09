from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class QuickNoteCreate(BaseModel):
    content: str
    source: str = "text"
    tags: List[str] = Field(default_factory=list)
    problem_id: Optional[UUID] = None
    source_turn_id: Optional[UUID] = None


class QuickNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    problem_id: Optional[UUID] = None
    source_turn_id: Optional[UUID] = None
    content: str
    source: str
    tags: List[str]
    created_at: datetime
