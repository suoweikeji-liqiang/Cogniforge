from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from datetime import datetime

LearningMode = Literal["socratic", "exploration"]


class ProblemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    associated_concepts: List[str] = Field(default_factory=list)
    learning_mode: LearningMode = "socratic"


class ProblemCreate(ProblemBase):
    pass


class ProblemUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    associated_concepts: Optional[List[str]] = None
    learning_mode: Optional[LearningMode] = None
    status: Optional[str] = None


class ProblemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    description: Optional[str]
    associated_concepts: List[str]
    learning_mode: LearningMode
    status: str
    created_at: datetime
    updated_at: datetime


class ProblemResponseCreate(BaseModel):
    problem_id: UUID
    user_response: str
    learning_mode: LearningMode = "socratic"


class ProblemResponseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    problem_id: UUID
    turn_id: Optional[UUID] = None
    learning_mode: LearningMode
    mode_metadata: Dict[str, Any] = Field(default_factory=dict)
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
    learning_mode: LearningMode = "exploration"
    answer_mode: str = Field(default="direct")


class LearningQuestionResponse(BaseModel):
    turn_id: Optional[UUID] = None
    learning_mode: LearningMode
    mode_metadata: Dict[str, Any] = Field(default_factory=dict)
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
    learning_mode: LearningMode
    source_turn_id: Optional[UUID] = None
    confidence: float
    status: str
    evidence_snippet: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class ProblemTurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    problem_id: UUID
    learning_mode: LearningMode
    step_index: Optional[int] = None
    user_text: Optional[str] = None
    assistant_text: Optional[str] = None
    mode_metadata: Dict[str, Any] = Field(default_factory=dict)
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
