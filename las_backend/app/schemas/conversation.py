from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class MessageBase(BaseModel):
    role: str
    content: str
    metadata: dict = {}


class MessageCreate(MessageBase):
    pass


class MessageResponse(MessageBase):
    id: UUID
    conversation_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationBase(BaseModel):
    title: Optional[str] = None
    problem_id: Optional[UUID] = None


class ConversationCreate(ConversationBase):
    pass


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    messages: Optional[List[dict]] = None


class ConversationResponse(ConversationBase):
    id: UUID
    user_id: UUID
    messages: List[dict]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    conversation_id: Optional[UUID] = None
    problem_id: Optional[UUID] = None
    message: str
    generate_contradiction: bool = False
    suggest_migration: bool = False


class ChatResponse(BaseModel):
    message: str
    conversation_id: UUID
    metadata: dict = {}
