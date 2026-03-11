from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Literal, Optional, List
from uuid import UUID
from datetime import datetime


class ConceptMapNode(BaseModel):
    id: str
    label: str
    type: str


class ConceptMapEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None


class ConceptMap(BaseModel):
    nodes: List[ConceptMapNode] = Field(default_factory=list)
    edges: List[ConceptMapEdge] = Field(default_factory=list)


class ModelCardBase(BaseModel):
    title: str = Field(..., max_length=500)
    concept_maps: Optional[ConceptMap] = None
    user_notes: Optional[str] = None
    examples: List[str] = Field(default_factory=list)


class ModelCardCreate(ModelCardBase):
    pass


class ModelCardUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    concept_maps: Optional[ConceptMap] = None
    user_notes: Optional[str] = None
    examples: Optional[List[str]] = None
    counter_examples: Optional[List[str]] = None
    migration_attempts: Optional[List[dict]] = None
    change_reason: Optional[str] = Field(None, max_length=500)


ModelCardOriginType = Literal["manual", "problem_concept_candidate"]
ModelCardOriginStage = Literal[
    "manual_creation",
    "accepted_concept_candidate",
    "merged_concept_candidate",
]
ModelCardLifecycleStage = Literal["draft", "active"]
LearningMode = Literal["socratic", "exploration"]


class ModelCardResponse(ModelCardBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    lifecycle_stage: ModelCardLifecycleStage
    origin_type: ModelCardOriginType
    origin_stage: ModelCardOriginStage
    origin_problem_id: Optional[UUID] = None
    origin_problem_title: Optional[str] = None
    origin_concept_candidate_id: Optional[UUID] = None
    origin_source_turn_id: Optional[UUID] = None
    origin_learning_mode: Optional[LearningMode] = None
    origin_concept_text: Optional[str] = None
    counter_examples: List[str]
    migration_attempts: List[dict]
    version: int
    parent_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class ModelCardReviewScheduleSummary(BaseModel):
    schedule_id: UUID
    model_card_id: UUID
    next_review_at: datetime
    last_reviewed_at: Optional[datetime] = None
    recall_state: str
    recent_outcome: str
    recommended_action: str
    needs_reinforcement: bool = False
    reinforcement_target: Optional[dict[str, Any]] = None
    origin: Optional[dict[str, Any]] = None


class ModelCardListResponse(ModelCardResponse):
    is_scheduled: bool = False
    review_schedule: Optional[ModelCardReviewScheduleSummary] = None


class CounterExampleInput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: UUID
    concept: str


class MigrationInput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: UUID
    target_domain: str


# Evolution Log schemas
class EvolutionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID
    model_id: UUID
    user_id: UUID
    action_taken: Optional[str] = None
    previous_version_id: Optional[UUID] = None
    reason_for_change: Optional[str] = None
    snapshot: Optional[dict] = None
    created_at: datetime


class EvolutionCompare(BaseModel):
    old_version: Optional[dict] = None
    new_version: dict
    changes_summary: str
