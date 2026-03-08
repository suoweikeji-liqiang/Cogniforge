from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReviewBase(BaseModel):
    review_type: str
    period: str


class ReviewCreate(ReviewBase):
    content: dict


class ReviewGenerateRequest(ReviewBase):
    pass


class ReviewGenerateResponse(ReviewBase):
    content: dict


class ReviewUpdate(BaseModel):
    review_type: Optional[str] = None
    period: Optional[str] = None
    content: Optional[dict] = None


class ReviewResponse(ReviewBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    content: dict
    created_at: datetime
