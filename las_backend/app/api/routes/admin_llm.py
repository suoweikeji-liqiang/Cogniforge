from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.entities.llm_provider import LLMProvider, LLMModel
from app.models.entities.user import User
from app.api.routes.auth import get_current_user
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/admin/llm-config", tags=["Admin"])


class ProviderCreate(BaseModel):
    name: str
    provider_type: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    enabled: bool = True
    priority: int = 0


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None


class ModelCreate(BaseModel):
    provider_id: int
    model_id: str
    model_name: str
    enabled: bool = True
    is_default: bool = False


class ModelUpdate(BaseModel):
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/providers")
async def get_providers(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(
        select(LLMProvider).options(selectinload(LLMProvider.models))
    )
    providers = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "provider_type": p.provider_type,
            "api_key": p.api_key[:10] + "..." if p.api_key else None,
            "base_url": p.base_url,
            "enabled": p.enabled,
            "priority": p.priority,
            "models": [
                {
                    "id": m.id,
                    "model_id": m.model_id,
                    "model_name": m.model_name,
                    "enabled": m.enabled,
                    "is_default": m.is_default
                }
                for m in p.models
            ]
        }
        for p in providers
    ]


@router.post("/providers")
async def create_provider(
    provider: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    db_provider = LLMProvider(
        name=provider.name,
        provider_type=provider.provider_type,
        api_key=provider.api_key,
        base_url=provider.base_url,
        enabled=provider.enabled,
        priority=provider.priority
    )
    db.add(db_provider)
    await db.commit()
    await db.refresh(db_provider)
    return {"id": db_provider.id, "name": db_provider.name}


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: int,
    provider: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(
        select(LLMProvider).where(LLMProvider.id == provider_id)
    )
    db_provider = result.scalar_one_or_none()
    if not db_provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    if provider.name is not None:
        db_provider.name = provider.name
    if provider.provider_type is not None:
        db_provider.provider_type = provider.provider_type
    if provider.api_key is not None:
        db_provider.api_key = provider.api_key
    if provider.base_url is not None:
        db_provider.base_url = provider.base_url
    if provider.enabled is not None:
        db_provider.enabled = provider.enabled
    if provider.priority is not None:
        db_provider.priority = provider.priority
    
    await db.commit()
    return {"status": "success"}


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(
        select(LLMProvider).where(LLMProvider.id == provider_id)
    )
    db_provider = result.scalar_one_or_none()
    if not db_provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    await db.delete(db_provider)
    await db.commit()
    return {"status": "deleted"}


@router.post("/models")
async def create_model(
    model: ModelCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    if model.is_default:
        result = await db.execute(
            select(LLMModel).where(
                LLMModel.provider_id == model.provider_id,
                LLMModel.is_default == True
            )
        )
        existing_default = result.scalars().all()
        for m in existing_default:
            m.is_default = False
    
    db_model = LLMModel(
        provider_id=model.provider_id,
        model_id=model.model_id,
        model_name=model.model_name,
        enabled=model.enabled,
        is_default=model.is_default
    )
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    return {"id": db_model.id, "model_id": db_model.model_id}


@router.put("/models/{model_id}")
async def update_model(
    model_id: int,
    model: ModelUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == model_id)
    )
    db_model = result.scalar_one_or_none()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if model.is_default and model.is_default != db_model.is_default:
        result = await db.execute(
            select(LLMModel).where(
                LLMModel.provider_id == db_model.provider_id,
                LLMModel.is_default == True,
                LLMModel.id != model_id
            )
        )
        existing_default = result.scalars().all()
        for m in existing_default:
            m.is_default = False
    
    if model.model_id is not None:
        db_model.model_id = model.model_id
    if model.model_name is not None:
        db_model.model_name = model.model_name
    if model.enabled is not None:
        db_model.enabled = model.enabled
    if model.is_default is not None:
        db_model.is_default = model.is_default
    
    await db.commit()
    return {"status": "success"}


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == model_id)
    )
    db_model = result.scalar_one_or_none()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    await db.delete(db_model)
    await db.commit()
    return {"status": "deleted"}


@router.get("/providers/{provider_id}/test")
async def test_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(
        select(LLMProvider).options(selectinload(LLMProvider.models)).where(LLMProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    try:
        if provider.provider_type == "openai":
            import openai
            client = openai.OpenAI(api_key=provider.api_key, base_url=provider.base_url or None)
            response = client.chat.completions.create(
                model=provider.models[0].model_id if provider.models else "gpt-4o-mini",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10
            )
            return {"status": "success", "response": "Connected successfully"}
        
        elif provider.provider_type == "anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=provider.api_key, base_url=provider.base_url or None)
            response = client.messages.create(
                model=provider.models[0].model_id if provider.models else "claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            return {"status": "success", "response": "Connected successfully"}
        
        elif provider.provider_type == "ollama":
            import httpx
            base = provider.base_url or "http://localhost:11434"
            response = httpx.get(f"{base}/api/tags", timeout=5)
            if response.status_code == 200:
                return {"status": "success", "response": "Connected to Ollama"}
            raise Exception("Failed to connect")
        
        else:
            return {"status": "error", "message": f"Provider type {provider.provider_type} test not implemented"}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}
