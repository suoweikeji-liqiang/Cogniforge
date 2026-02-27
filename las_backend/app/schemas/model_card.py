from pydantic import BaseModel, Field
from typing import Optional, List
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
    nodes: List[ConceptMapNode] = []
    edges: List[ConceptMapEdge] = []


class ModelCardBase(BaseModel):
    title: str = Field(..., max_length=500)
    concept_maps: Optional[ConceptMap] = None
    user_notes: Optional[str] = None
    examples: List[str] = []


class ModelCardCreate(ModelCardBase):
    pass


class ModelCardUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    concept_maps: Optional[ConceptMap] = None
    user_notes: Optional[str] = None
    examples: Optional[List[str]] = None
    counter_examples: Optional[List[str]] = None
    migration_attempts: Optional[List[dict]] = None


class ModelCardResponse(ModelCardBase):
    id: UUID
    user_id: UUID
    counter_examples: List[str]
    migration_attempts: List[dict]
    version: int
    parent_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CounterExampleInput(BaseModel):
    model_id: UUID
    concept: str


class MigrationInput(BaseModel):
    model_id: UUID
    target_domain: str


# Evolution Log schemas
class EvolutionLogResponse(BaseModel):
    id: UUID
    model_id: UUID
    user_id: UUID
    action_taken: Optional[str] = None
    previous_version_id: Optional[UUID] = None
    reason_for_change: Optional[str] = None
    snapshot: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EvolutionCompare(BaseModel):
    old_version: Optional[dict] = None
    new_version: dict
    changes_summary: str
