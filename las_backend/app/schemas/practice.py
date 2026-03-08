from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
