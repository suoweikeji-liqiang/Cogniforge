from datetime import datetime
from typing import List, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetrievalItemResponse(BaseModel):
    entity_type: str
    entity_id: str
    title: str
    score: float
    preview: Optional[str] = None


class RetrievalEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    source: str
    query: str
    retrieval_context: Optional[str]
    items: List[RetrievalItemResponse] = Field(default_factory=list)
    result_count: int
    created_at: datetime


class RetrievalSummaryResponse(BaseModel):
    total_events: int
    total_hits: int
    average_hits: float
    zero_hit_events: int
    poor_hit_events: int
    zero_hit_rate: float
    health_status: str
    source_breakdown: Dict[str, int] = Field(default_factory=dict)
