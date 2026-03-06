from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


class ProblemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    associated_concepts: List[str] = Field(default_factory=list)


class ProblemCreate(ProblemBase):
    pass


class ProblemUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    associated_concepts: Optional[List[str]] = None
    status: Optional[str] = None


class ProblemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    description: Optional[str]
    associated_concepts: List[str]
    status: str
    created_at: datetime
    updated_at: datetime


class ProblemResponseCreate(BaseModel):
    problem_id: UUID
    user_response: str


class ProblemResponseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    problem_id: UUID
    user_response: str
    system_feedback: Optional[str]
    structured_feedback: Optional[dict] = None
    auto_advanced: Optional[bool] = None
    new_current_step: Optional[int] = None
    new_concepts: Optional[List[str]] = None
    accepted_concepts: Optional[List[str]] = None
    pending_concepts: Optional[List[str]] = None
    concepts_updated: Optional[bool] = None
    trace_id: Optional[str] = None
    llm_calls: Optional[int] = None
    llm_latency_ms: Optional[int] = None
    fallback_reason: Optional[str] = None
    created_at: datetime


class LearningPathStep(BaseModel):
    step: int
    concept: str
    description: str
    resources: List[str] = Field(default_factory=list)


class LearningPathProgressUpdate(BaseModel):
    current_step: int


class LearningPathResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    problem_id: UUID
    path_data: List[LearningPathStep]
    current_step: int


class LearningStepHintResponse(BaseModel):
    step_index: int
    step_concept: str
    hint: str
    structured_hint: Optional[dict] = None


class LearningQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    answer_mode: str = Field(default="direct")


class LearningQuestionResponse(BaseModel):
    question: str
    answer: str
    answer_mode: str
    step_index: int
    step_concept: str
    suggested_next_focus: Optional[str] = None
    accepted_concepts: Optional[List[str]] = None
    pending_concepts: Optional[List[str]] = None
    trace_id: Optional[str] = None
    llm_calls: Optional[int] = None
    llm_latency_ms: Optional[int] = None
    fallback_reason: Optional[str] = None


class ProblemConceptCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    problem_id: UUID
    concept_text: str
    source: str
    confidence: float
    status: str
    evidence_snippet: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class ProblemConceptCandidateActionResponse(BaseModel):
    candidate: ProblemConceptCandidateResponse
    accepted_concepts: List[str] = Field(default_factory=list)
    trace_id: Optional[str] = None


class ProblemConceptRollbackRequest(BaseModel):
    concept_text: str = Field(..., min_length=1, max_length=120)
    reason: Optional[str] = Field(default=None, max_length=500)


class ProblemConceptRollbackResponse(BaseModel):
    removed: bool
    concept_text: str
    associated_concepts: List[str] = Field(default_factory=list)
    trace_id: Optional[str] = None
