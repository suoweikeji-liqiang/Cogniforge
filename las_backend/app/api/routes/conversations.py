from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.models.entities.user import User, Conversation, ConversationMessage
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ChatRequest,
    ChatResponse,
    MessageResponse,
)
from app.api.routes.auth import get_current_user
from app.services.model_os_service import model_os_service

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post("/", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    conv_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    db_conv = Conversation(
        user_id=current_user.id,
        problem_id=conv_data.problem_id,
        title=conv_data.title or "New Conversation",
        messages=[],
    )
    
    db.add(db_conv)
    await db.commit()
    await db.refresh(db_conv)
    
    return db_conv


@router.get("/", response_model=List[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    return conversations


@router.get("/{conv_id}", response_model=ConversationResponse)
async def get_conversation(
    conv_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conv


@router.delete("/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    await db.delete(conv)
    await db.commit()
    
    return None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    chat_data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    conv = None
    
    if chat_data.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == chat_data.conversation_id,
                Conversation.user_id == current_user.id
            )
        )
        conv = result.scalar_one_or_none()
    
    if not conv and chat_data.problem_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.problem_id == chat_data.problem_id,
                Conversation.user_id == current_user.id
            )
        )
        conv = result.scalar_one_or_none()
    
    if not conv:
        conv = Conversation(
            user_id=current_user.id,
            problem_id=chat_data.problem_id,
            title="Chat",
            messages=[],
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
    
    messages = conv.messages or []
    messages.append({"role": "user", "content": chat_data.message})
    
    response_content = await model_os_service.generate_with_context(
        prompt=chat_data.message,
        context=messages,
    )
    
    messages.append({"role": "assistant", "content": response_content})
    conv.messages = messages
    
    metadata = {}
    
    if chat_data.generate_contradiction:
        counter_examples = await model_os_service.generate_counter_examples(
            model_title=conv.title or "Current Topic",
            model_concepts=[],
            user_response=chat_data.message,
        )
        metadata["counter_examples"] = counter_examples
    
    if chat_data.suggest_migration:
        migrations = await model_os_service.suggest_migration(
            model_title=conv.title or "Current Topic",
            model_concepts=[],
        )
        metadata["migrations"] = migrations
    
    await db.commit()
    await db.refresh(conv)
    
    return ChatResponse(
        message=response_content,
        conversation_id=conv.id,
        metadata=metadata,
    )
