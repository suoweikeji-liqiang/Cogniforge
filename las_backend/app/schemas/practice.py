from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class PracticeTaskBase(BaseModel):
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    task_type: Optional[str] = None


class PracticeTaskCreate(PracticeTaskBase):
    model_card_id: Optional[UUID] = None


class PracticeTaskResponse(PracticeTaskBase):
    id: UUID
    model_card_id: Optional[UUID]
    created_at: datetime
    
    class Config:
        from_attributes = True


class PracticeSubmissionCreate(BaseModel):
    practice_task_id: UUID
    solution: str


class PracticeSubmissionResponse(BaseModel):
    id: UUID
    user_id: UUID
    practice_task_id: UUID
    solution: str
    feedback: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ReviewBase(BaseModel):
    review_type: str
    period: str


class ReviewCreate(ReviewBase):
    content: dict


class ReviewResponse(ReviewBase):
    id: UUID
    user_id: UUID
    content: dict
    created_at: datetime
    
    class Config:
        from_attributes = True
