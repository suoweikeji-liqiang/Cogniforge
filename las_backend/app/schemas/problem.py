from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from datetime import datetime
from app.schemas.model_card import ModelCardResponse

LearningMode = Literal["socratic", "exploration"]
SocraticQuestionKind = Literal["probe", "checkpoint"]
ExplorationAnswerType = Literal[
    "concept_explanation",
    "boundary_clarification",
    "misconception_correction",
    "comparison",
    "prerequisite_explanation",
    "worked_example",
]
PathSuggestionType = Literal["prerequisite", "branch_deep_dive", "comparison_path"]
PathInsertionBehavior = Literal[
    "insert_before_current_main",
    "save_as_side_branch",
    "bookmark_for_later",
]
PathCandidateStatus = Literal["pending", "planned", "bookmarked", "dismissed"]
LearningPathKind = Literal["main", "branch", "prerequisite", "comparison"]
ConceptCandidateStatus = Literal["pending", "accepted", "rejected", "reverted", "postponed", "merged"]


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
    question_kind: Optional[SocraticQuestionKind] = None
    socratic_question: Optional[str] = Field(default=None, max_length=2000)


class TurnEvaluationResponse(BaseModel):
    mastery_score: int
    dimension_scores: Dict[str, int] = Field(default_factory=dict)
    confidence: float
    correctness: str = ""


class TurnDecisionResponse(BaseModel):
    advance: bool
    progression_ran: bool
    reason: str = ""


class TurnFollowUpResponse(BaseModel):
    needed: bool
    question: Optional[str] = None
    question_kind: Optional[SocraticQuestionKind] = None


class ProblemPathCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    problem_id: UUID
    learning_mode: LearningMode
    source_turn_id: Optional[UUID] = None
    step_index: Optional[int] = None
    type: PathSuggestionType
    title: str
    reason: Optional[str] = None
    recommended_insertion: PathInsertionBehavior
    selected_insertion: Optional[PathInsertionBehavior] = None
    status: PathCandidateStatus
    evidence_snippet: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class ProblemPathCandidateDecisionRequest(BaseModel):
    action: Literal[
        "insert_before_current_main",
        "save_as_side_branch",
        "bookmark_for_later",
        "dismiss",
    ]


class ProblemPathCandidateDecisionResponse(BaseModel):
    candidate: ProblemPathCandidateResponse
    trace_id: Optional[str] = None


class ProblemResponseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    problem_id: UUID
    turn_id: Optional[UUID] = None
    learning_mode: LearningMode
    mode_metadata: Dict[str, Any] = Field(default_factory=dict)
    question_kind: Optional[SocraticQuestionKind] = None
    socratic_question: Optional[str] = None
    evaluation: Optional[TurnEvaluationResponse] = None
    decision: Optional[TurnDecisionResponse] = None
    follow_up: Optional[TurnFollowUpResponse] = None
    user_response: str
    system_feedback: Optional[str]
    structured_feedback: Optional[dict] = None
    auto_advanced: Optional[bool] = None
    new_current_step: Optional[int] = None
    new_concepts: Optional[List[str]] = None
    accepted_concepts: Optional[List[str]] = None
    pending_concepts: Optional[List[str]] = None
    derived_path_candidates: List[ProblemPathCandidateResponse] = Field(default_factory=list)
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
    title: Optional[str] = None
    kind: LearningPathKind = "main"
    parent_path_id: Optional[UUID] = None
    source_turn_id: Optional[UUID] = None
    return_step_id: Optional[int] = None
    branch_reason: Optional[str] = None
    is_active: bool = True
    path_data: List[LearningPathStep]
    current_step: int


class LearningStepHintResponse(BaseModel):
    step_index: int
    step_concept: str
    hint: str
    structured_hint: Optional[dict] = None


class SocraticQuestionResponse(BaseModel):
    learning_mode: LearningMode
    step_index: int
    step_concept: str
    question_kind: SocraticQuestionKind
    question: str
    mode_metadata: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None
    llm_calls: Optional[int] = None
    llm_latency_ms: Optional[int] = None
    fallback_reason: Optional[str] = None


class LearningQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    learning_mode: LearningMode = "exploration"
    answer_mode: str = Field(default="direct")


class ExplorationDerivedCandidateResponse(BaseModel):
    name: str
    confidence: float
    status: Optional[str] = None


class ExplorationPathSuggestionResponse(BaseModel):
    type: PathSuggestionType
    title: str
    reason: Optional[str] = None


class LearningQuestionResponse(BaseModel):
    turn_id: Optional[UUID] = None
    learning_mode: LearningMode
    mode_metadata: Dict[str, Any] = Field(default_factory=dict)
    question: str
    answer: str
    answer_mode: str
    answer_type: ExplorationAnswerType = "concept_explanation"
    answered_concepts: List[str] = Field(default_factory=list)
    related_concepts: List[str] = Field(default_factory=list)
    derived_candidates: List[ExplorationDerivedCandidateResponse] = Field(default_factory=list)
    derived_path_candidates: List[ProblemPathCandidateResponse] = Field(default_factory=list)
    next_learning_actions: List[str] = Field(default_factory=list)
    path_suggestions: List[ExplorationPathSuggestionResponse] = Field(default_factory=list)
    return_to_main_path_hint: bool = True
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
    status: ConceptCandidateStatus
    merged_into_concept: Optional[str] = None
    linked_model_card_id: Optional[UUID] = None
    evidence_snippet: Optional[str] = None
    source_turn_preview: Optional[str] = None
    source_turn_created_at: Optional[datetime] = None
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


class ProblemConceptCandidateHandoffResponse(BaseModel):
    candidate: ProblemConceptCandidateResponse
    model_card: ModelCardResponse
    created_model_card: bool = False
    review_scheduled: bool = False
    next_review_at: Optional[datetime] = None
    trace_id: Optional[str] = None


class ProblemConceptCandidateMergeRequest(BaseModel):
    target_concept_text: str = Field(..., min_length=1, max_length=120)


class ProblemConceptRollbackRequest(BaseModel):
    concept_text: str = Field(..., min_length=1, max_length=120)
    reason: Optional[str] = Field(default=None, max_length=500)


class ProblemConceptRollbackResponse(BaseModel):
    removed: bool
    concept_text: str
    associated_concepts: List[str] = Field(default_factory=list)
    trace_id: Optional[str] = None
