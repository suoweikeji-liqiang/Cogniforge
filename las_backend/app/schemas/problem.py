from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class ProblemBase(BaseModel):
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    associated_concepts: List[str] = []


class ProblemCreate(ProblemBase):
    pass


class ProblemUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    associated_concepts: Optional[List[str]] = None
    status: Optional[str] = None


class ProblemResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: Optional[str]
    associated_concepts: List[str]
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProblemResponseCreate(BaseModel):
    problem_id: UUID
    user_response: str


class ProblemResponseResponse(BaseModel):
    id: UUID
    problem_id: UUID
    user_response: str
    system_feedback: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class LearningPathStep(BaseModel):
    step: int
    concept: str
    description: str
    resources: List[str] = []


class LearningPathResponse(BaseModel):
    id: UUID
    problem_id: UUID
    path_data: List[LearningPathStep]
    current_step: int
    
    class Config:
        from_attributes = True
