from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class PracticeTaskBase(BaseModel):
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    task_type: Optional[str] = None


class PracticeTaskCreate(PracticeTaskBase):
    model_config = ConfigDict(protected_namespaces=())

    model_card_id: Optional[UUID] = None


class PracticeTaskResponse(PracticeTaskBase):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID
    user_id: Optional[UUID]
    model_card_id: Optional[UUID]
    created_at: datetime


class PracticeSubmissionCreate(BaseModel):
    practice_task_id: UUID
    solution: str


class PracticeSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    practice_task_id: UUID
    solution: str
    feedback: Optional[str]
    structured_feedback: Optional[dict] = None
    created_at: datetime


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
