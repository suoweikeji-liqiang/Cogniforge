from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class ResourceLinkCreate(BaseModel):
    url: str
    title: Optional[str] = None
    link_type: str = "webpage"


class ResourceLinkUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class ResourceLinkResponse(BaseModel):
    id: UUID
    user_id: UUID
    url: str
    title: Optional[str]
    link_type: str
    ai_summary: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
