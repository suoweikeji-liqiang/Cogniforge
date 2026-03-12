from __future__ import annotations

import asyncio
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
import openai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.entities.llm_provider import LLMProvider, LLMModel

OPENAI_COMPATIBLE_PROVIDERS = {"openai", "qwen"}
DEFAULT_BASE_URLS = {
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}


class LLMService:
    def __init__(self):
        self.settings = get_settings()
    
    async def _get_db(self):
        async with AsyncSessionLocal() as session:
            yield session
    
    async def _get_active_provider(self, db: AsyncSession, provider_type: Optional[str] = None):
        query = select(LLMProvider).where(LLMProvider.enabled == True)
        if provider_type:
            query = query.where(LLMProvider.provider_type == provider_type)
        query = query.order_by(LLMProvider.priority.desc())
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_default_model(self, db: AsyncSession, provider_id: int):
        result = await db.execute(
            select(LLMModel).where(
                LLMModel.provider_id == provider_id,
                LLMModel.enabled == True,
                LLMModel.is_default == True
            )
        )
        return result.scalar_one_or_none()

    async def _resolve_provider_and_model(
        self,
        db: AsyncSession,
        provider_type: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> tuple[Optional[LLMProvider], str]:
        provider = await self._get_active_provider(db, provider_type)
        if not provider:
            return None, ""

        resolved_model_id = model_id
        if not resolved_model_id:
            default_model = await self._get_default_model(db, provider.id)
            if default_model:
                resolved_model_id = default_model.model_id

        fallbacks = {
            "openai": "gpt-4o-mini",
            "qwen": "qwen-plus",
            "anthropic": "claude-3-5-sonnet-20241022",
            "ollama": "llama2",
        }
        return provider, resolved_model_id or fallbacks.get(provider.provider_type, "gpt-4o-mini")
    
    async def generate(
        self,
        prompt: str,
        provider_type: Optional[str] = None,
        model_id: Optional[str] = None,
        **kwargs
    ) -> str:
        async with AsyncSessionLocal() as db:
            provider, resolved_model = await self._resolve_provider_and_model(
                db,
                provider_type=provider_type,
                model_id=model_id,
            )
            if not provider:
                return "Error: No active LLM provider configured"

            if provider.provider_type in OPENAI_COMPATIBLE_PROVIDERS:
                return await self._generate_openai_compatible(prompt, provider, resolved_model)
            elif provider.provider_type == "anthropic":
                return await self._generate_anthropic(prompt, provider, resolved_model)
            elif provider.provider_type == "ollama":
                return await self._generate_ollama(prompt, provider, resolved_model)
            else:
                return f"Error: Unsupported provider type: {provider.provider_type}"

    async def generate_structured_json(
        self,
        prompt: str,
        json_schema: Dict[str, Any],
        *,
        schema_name: str = "structured_response",
        provider_type: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any] | List[Any]]:
        async with AsyncSessionLocal() as db:
            provider, resolved_model = await self._resolve_provider_and_model(
                db,
                provider_type=provider_type,
                model_id=model_id,
            )
            if not provider:
                return None

            if provider.provider_type not in OPENAI_COMPATIBLE_PROVIDERS:
                return None

            return await self._generate_openai_compatible_structured(
                prompt=prompt,
                provider=provider,
                model=resolved_model,
                json_schema=json_schema,
                schema_name=schema_name,
            )
    
    async def _generate_openai_compatible(self, prompt: str, provider: LLMProvider, model: str) -> str:
        try:
            def _call() -> str:
                client = openai.OpenAI(
                    api_key=provider.api_key,
                    base_url=provider.base_url or DEFAULT_BASE_URLS.get(provider.provider_type) or None,
                )
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    timeout=self.settings.LLM_REQUEST_TIMEOUT_SECONDS,
                )
                return response.choices[0].message.content

            return await asyncio.to_thread(_call)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return f"Error generating response: {str(e)}"

    async def _generate_openai_compatible_structured(
        self,
        *,
        prompt: str,
        provider: LLMProvider,
        model: str,
        json_schema: Dict[str, Any],
        schema_name: str,
    ) -> Optional[Dict[str, Any] | List[Any]]:
        try:
            def _call() -> Optional[Dict[str, Any] | List[Any]]:
                client = openai.OpenAI(
                    api_key=provider.api_key,
                    base_url=provider.base_url or DEFAULT_BASE_URLS.get(provider.provider_type) or None,
                )
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "schema": json_schema,
                            "strict": True,
                        },
                    },
                    timeout=self.settings.LLM_REQUEST_TIMEOUT_SECONDS,
                )
                message = response.choices[0].message if response.choices else None
                content = getattr(message, "content", None) if message else None
                if not content:
                    return None
                return json.loads(content)

            return await asyncio.to_thread(_call)
        except asyncio.CancelledError:
            raise
        except Exception:
            return None
    
    async def _generate_anthropic(self, prompt: str, provider: LLMProvider, model: str) -> str:
        try:
            def _call() -> str:
                from anthropic import Anthropic

                client = Anthropic(
                    api_key=provider.api_key,
                    base_url=provider.base_url or None
                )
                response = client.messages.create(
                    model=model,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text

            return await asyncio.to_thread(_call)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    async def _generate_ollama(self, prompt: str, provider: LLMProvider, model: str) -> str:
        try:
            def _call() -> str:
                import httpx

                base_url = provider.base_url or "http://localhost:11434"
                response = httpx.post(
                    f"{base_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                    timeout=self.settings.LLM_REQUEST_TIMEOUT_SECONDS,
                )
                if response.status_code == 200:
                    return response.json().get("response", "No response")
                return f"Error: {response.status_code}"

            return await asyncio.to_thread(_call)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    async def stream_generate(
        self,
        messages: list[dict],
        system_prompt: str = "",
        provider_type: str | None = None,
        model_id: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        async with AsyncSessionLocal() as db:
            provider, resolved_model = await self._resolve_provider_and_model(
                db,
                provider_type=provider_type,
                model_id=model_id,
            )
            if not provider:
                yield "Error: No active LLM provider configured"
                return

            if provider.provider_type in OPENAI_COMPATIBLE_PROVIDERS:
                async for token in self._stream_openai_compatible(messages, system_prompt, provider, resolved_model, temperature):
                    yield token
            elif provider.provider_type == "anthropic":
                async for token in self._stream_anthropic(messages, system_prompt, provider, resolved_model, temperature):
                    yield token
            else:
                yield f"Error: Streaming not supported for provider: {provider.provider_type}"

    async def _stream_openai_compatible(
        self,
        messages: list[dict],
        system_prompt: str,
        provider,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        try:
            client = openai.AsyncOpenAI(
                api_key=provider.api_key,
                base_url=provider.base_url or DEFAULT_BASE_URLS.get(provider.provider_type) or None,
            )
            all_messages = []
            if system_prompt:
                all_messages.append({"role": "system", "content": system_prompt})
            all_messages.extend(messages)

            stream = await client.chat.completions.create(
                model=model,
                messages=all_messages,
                temperature=temperature,
                stream=True,
                timeout=self.settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content if chunk.choices else None
                if content is not None:
                    yield content
        except Exception as e:
            yield f"Error: {str(e)}"

    async def _stream_anthropic(
        self,
        messages: list[dict],
        system_prompt: str,
        provider,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(
                api_key=provider.api_key,
                base_url=provider.base_url or None,
            )
            kwargs: dict = {
                "model": model,
                "max_tokens": 2048,
                "messages": messages,
                "temperature": temperature,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            yield f"Error: {str(e)}"

    def _build_context_prompt(
        self,
        prompt: str,
        context: List[Dict[str, Any]],
        retrieval_context: Optional[str] = None,
    ) -> str:
        context_str = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in context
        ])
        retrieval_block = f"\nRelevant knowledge:\n{retrieval_context}\n" if retrieval_context else ""
        language_instruction = (
            "Language requirement: Use the current question as the source of truth for language. "
            "Respond in the same language as the current question. "
            "If the current question contains Chinese, respond in Simplified Chinese. "
            "If the current question does not contain Chinese, do not respond in Chinese even if other context does."
        )

        return f"""Context:
{context_str}
{retrieval_block}

Current question: {prompt}

{language_instruction}"""

    async def generate_with_context(
        self,
        prompt: str,
        context: List[Dict[str, Any]],
        retrieval_context: Optional[str] = None,
        provider_type: Optional[str] = None,
    ) -> str:
        full_prompt = self._build_context_prompt(
            prompt=prompt,
            context=context,
            retrieval_context=retrieval_context,
        )
        return await self.generate(full_prompt, provider_type)

    async def stream_generate_with_context(
        self,
        prompt: str,
        context: List[Dict[str, Any]],
        retrieval_context: Optional[str] = None,
        provider_type: Optional[str] = None,
        model_id: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        full_prompt = self._build_context_prompt(
            prompt=prompt,
            context=context,
            retrieval_context=retrieval_context,
        )
        async for token in self.stream_generate(
            messages=[{"role": "user", "content": full_prompt}],
            provider_type=provider_type,
            model_id=model_id,
            temperature=temperature,
        ):
            yield token


llm_service = LLMService()
