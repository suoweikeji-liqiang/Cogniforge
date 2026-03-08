from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime


class ResourceLinkCreate(BaseModel):
    url: str
    title: Optional[str] = None
    link_type: str = "webpage"
    problem_id: Optional[UUID] = None
    source_turn_id: Optional[UUID] = None


class ResourceLinkUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class ResourceLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    problem_id: Optional[UUID]
    source_turn_id: Optional[UUID]
    url: str
    title: Optional[str]
    link_type: str
    ai_summary: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
