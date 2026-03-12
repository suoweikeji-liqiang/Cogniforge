import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities.llm_provider import LLMProvider, LLMModel
from app.models.entities.system_settings import SystemSettings
from app.models.entities.user import User
from app.api.deps import require_admin
from app.services.llm_service import DEFAULT_BASE_URLS, OPENAI_COMPATIBLE_PROVIDERS
from app.services.model_os_service import LLM_TASK_ROUTES_KEY
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/admin/llm-config", tags=["Admin"])
TASK_ROUTE_KEYS = ("interactive", "structured_heavy", "fallback")


def _provider_test_timeout_seconds() -> float:
    return float(max(5, min(int(get_settings().LLM_REQUEST_TIMEOUT_SECONDS), 12)))


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
    model_config = ConfigDict(protected_namespaces=())

    provider_id: int
    model_id: str
    model_name: str
    enabled: bool = True
    is_default: bool = False


class ModelUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: Optional[str] = None
    model_name: Optional[str] = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class TaskRouteSelection(BaseModel):
    provider_id: Optional[int] = None
    model_record_id: Optional[int] = None


class TaskRouteConfigUpdate(BaseModel):
    interactive: TaskRouteSelection = TaskRouteSelection()
    structured_heavy: TaskRouteSelection = TaskRouteSelection()
    fallback: TaskRouteSelection = TaskRouteSelection()


async def _get_task_routes_setting(db: AsyncSession) -> Optional[SystemSettings]:
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == LLM_TASK_ROUTES_KEY)
    )
    return result.scalar_one_or_none()


def _empty_task_routes_payload() -> Dict[str, Dict[str, Optional[int]]]:
    return {
        key: {"provider_id": None, "model_record_id": None}
        for key in TASK_ROUTE_KEYS
    }


def _normalize_route_payload(raw_value: Any) -> Dict[str, Dict[str, Optional[int]]]:
    payload = _empty_task_routes_payload()
    if not isinstance(raw_value, dict):
        return payload

    for key in TASK_ROUTE_KEYS:
        entry = raw_value.get(key)
        if not isinstance(entry, dict):
            continue
        provider_id = entry.get("provider_id")
        model_record_id = entry.get("model_record_id")
        payload[key] = {
            "provider_id": int(provider_id) if isinstance(provider_id, int) else None,
            "model_record_id": int(model_record_id) if isinstance(model_record_id, int) else None,
        }
    return payload


async def _load_task_routes_payload(db: AsyncSession) -> Dict[str, Dict[str, Optional[int]]]:
    setting = await _get_task_routes_setting(db)
    value = setting.value if setting else {}
    return _normalize_route_payload(value)


async def _validate_task_routes_payload(
    db: AsyncSession,
    payload: Dict[str, Dict[str, Optional[int]]],
) -> Dict[str, Dict[str, Optional[int]]]:
    normalized = _empty_task_routes_payload()

    for route_key in TASK_ROUTE_KEYS:
        entry = payload.get(route_key, {})
        provider_id = entry.get("provider_id")
        model_record_id = entry.get("model_record_id")

        if provider_id is None:
            normalized[route_key] = {"provider_id": None, "model_record_id": None}
            continue

        provider = await db.get(LLMProvider, int(provider_id))
        if not provider or not provider.enabled:
            raise HTTPException(status_code=400, detail=f"Invalid provider for route '{route_key}'")

        if model_record_id is None:
            normalized[route_key] = {"provider_id": provider.id, "model_record_id": None}
            continue

        model = await db.get(LLMModel, int(model_record_id))
        if not model or not model.enabled or model.provider_id != provider.id:
            raise HTTPException(status_code=400, detail=f"Invalid model for route '{route_key}'")

        normalized[route_key] = {"provider_id": provider.id, "model_record_id": model.id}

    return normalized


async def _save_task_routes_payload(
    db: AsyncSession,
    payload: Dict[str, Dict[str, Optional[int]]],
) -> None:
    setting = await _get_task_routes_setting(db)
    if setting:
        setting.value = payload
        setting.description = "Task-based LLM routing for interactive, structured-heavy, and fallback lanes."
    else:
        db.add(
            SystemSettings(
                key=LLM_TASK_ROUTES_KEY,
                value=payload,
                description="Task-based LLM routing for interactive, structured-heavy, and fallback lanes.",
            )
        )
    await db.commit()


async def _build_task_routes_response(
    db: AsyncSession,
    payload: Dict[str, Dict[str, Optional[int]]],
) -> Dict[str, Dict[str, Optional[Any]]]:
    response = _empty_task_routes_payload()

    for route_key in TASK_ROUTE_KEYS:
        entry = payload.get(route_key, {})
        provider_id = entry.get("provider_id")
        model_record_id = entry.get("model_record_id")
        provider = await db.get(LLMProvider, provider_id) if provider_id is not None else None
        model = await db.get(LLMModel, model_record_id) if model_record_id is not None else None
        response[route_key] = {
            "provider_id": provider.id if provider else None,
            "provider_name": provider.name if provider else None,
            "model_record_id": model.id if model else None,
            "model_name": model.model_name if model else None,
            "model_id": model.model_id if model else None,
        }

    return response


async def _cleanup_task_routes_for_provider(
    db: AsyncSession,
    provider_id: int,
) -> None:
    payload = await _load_task_routes_payload(db)
    changed = False
    for route_key in TASK_ROUTE_KEYS:
        entry = payload.get(route_key, {})
        if entry.get("provider_id") == provider_id:
            payload[route_key] = {"provider_id": None, "model_record_id": None}
            changed = True
    if changed:
        await _save_task_routes_payload(db, payload)


async def _cleanup_task_routes_for_model(
    db: AsyncSession,
    model_record_id: int,
) -> None:
    payload = await _load_task_routes_payload(db)
    changed = False
    for route_key in TASK_ROUTE_KEYS:
        entry = payload.get(route_key, {})
        if entry.get("model_record_id") == model_record_id:
            payload[route_key]["model_record_id"] = None
            changed = True
    if changed:
        await _save_task_routes_payload(db, payload)


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
            "api_key": "Configured" if p.api_key else None,
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


@router.get("/routes")
async def get_task_routes(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    payload = await _load_task_routes_payload(db)
    return await _build_task_routes_response(db, payload)


@router.put("/routes")
async def update_task_routes(
    routes: TaskRouteConfigUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    payload = routes.model_dump()
    normalized = await _validate_task_routes_payload(db, payload)
    await _save_task_routes_payload(db, normalized)
    return await _build_task_routes_response(db, normalized)


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
    if provider.enabled is False:
        await _cleanup_task_routes_for_provider(db, db_provider.id)
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
    await _cleanup_task_routes_for_provider(db, db_provider.id)
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
    if model.enabled is False:
        await _cleanup_task_routes_for_model(db, db_model.id)
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
    await _cleanup_task_routes_for_model(db, db_model.id)
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

    model_id = (
        provider.models[0].model_id
        if provider.models
        else ("qwen-plus" if provider.provider_type == "qwen" else "gpt-4o-mini")
    )

    def _run_provider_test() -> dict:
        if provider.provider_type in OPENAI_COMPATIBLE_PROVIDERS:
            import openai

            client = openai.OpenAI(
                api_key=provider.api_key,
                base_url=provider.base_url or DEFAULT_BASE_URLS.get(provider.provider_type) or None,
            )
            client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10,
                timeout=_provider_test_timeout_seconds(),
            )
            return {"status": "success", "response": "Connected successfully"}

        if provider.provider_type == "anthropic":
            from anthropic import Anthropic

            client = Anthropic(api_key=provider.api_key, base_url=provider.base_url or None)
            client.messages.create(
                model=model_id if provider.models else "claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
                timeout=_provider_test_timeout_seconds(),
            )
            return {"status": "success", "response": "Connected successfully"}

        if provider.provider_type == "ollama":
            import httpx

            base = provider.base_url or "http://localhost:11434"
            response = httpx.get(f"{base}/api/tags", timeout=min(_provider_test_timeout_seconds(), 5))
            if response.status_code == 200:
                return {"status": "success", "response": "Connected to Ollama"}
            raise RuntimeError("Failed to connect")

        return {"status": "error", "message": f"Provider type {provider.provider_type} test not implemented"}

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_run_provider_test),
            timeout=_provider_test_timeout_seconds(),
        )
    except asyncio.TimeoutError:
        return {
            "status": "error",
            "message": "Connection test timed out. Check model, base URL, or network.",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
