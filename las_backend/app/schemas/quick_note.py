from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class QuickNoteCreate(BaseModel):
    content: str
    source: str = "text"
    tags: List[str] = Field(default_factory=list)


class QuickNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    content: str
    source: str
    tags: List[str]
    created_at: datetime
