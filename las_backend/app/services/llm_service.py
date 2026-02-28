from typing import Optional, List, Dict, Any, AsyncGenerator
import openai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.models.entities.llm_provider import LLMProvider, LLMModel


class LLMService:
    def __init__(self):
        pass
    
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
    
    async def generate(
        self,
        prompt: str,
        provider_type: Optional[str] = None,
        model_id: Optional[str] = None,
        **kwargs
    ) -> str:
        async with AsyncSessionLocal() as db:
            provider = await self._get_active_provider(db, provider_type)
            if not provider:
                return "Error: No active LLM provider configured"

            # Use caller-specified model, or DB-configured default, or hardcoded fallback
            if not model_id:
                default_model = await self._get_default_model(db, provider.id)
                if default_model:
                    model_id = default_model.model_id

            fallbacks = {
                "openai": "gpt-4o-mini",
                "anthropic": "claude-3-5-sonnet-20241022",
                "ollama": "llama2",
            }
            resolved_model = model_id or fallbacks.get(provider.provider_type, "gpt-4o-mini")

            if provider.provider_type == "openai":
                return await self._generate_openai(prompt, provider, resolved_model)
            elif provider.provider_type == "anthropic":
                return await self._generate_anthropic(prompt, provider, resolved_model)
            elif provider.provider_type == "ollama":
                return await self._generate_ollama(prompt, provider, resolved_model)
            else:
                return f"Error: Unsupported provider type: {provider.provider_type}"
    
    async def _generate_openai(self, prompt: str, provider: LLMProvider, model: str) -> str:
        try:
            client = openai.OpenAI(
                api_key=provider.api_key,
                base_url=provider.base_url or None
            )
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    async def _generate_anthropic(self, prompt: str, provider: LLMProvider, model: str) -> str:
        try:
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
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    async def _generate_ollama(self, prompt: str, provider: LLMProvider, model: str) -> str:
        try:
            import httpx
            base_url = provider.base_url or "http://localhost:11434"
            response = httpx.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=60
            )
            if response.status_code == 200:
                return response.json().get("response", "No response")
            return f"Error: {response.status_code}"
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
            provider = await self._get_active_provider(db, provider_type)
            if not provider:
                yield "Error: No active LLM provider configured"
                return

            if not model_id:
                default_model = await self._get_default_model(db, provider.id)
                if default_model:
                    model_id = default_model.model_id

            fallbacks = {
                "openai": "gpt-4o-mini",
                "anthropic": "claude-3-5-sonnet-20241022",
                "ollama": "llama2",
            }
            resolved_model = model_id or fallbacks.get(provider.provider_type, "gpt-4o-mini")

            if provider.provider_type == "openai":
                async for token in self._stream_openai(messages, system_prompt, provider, resolved_model, temperature):
                    yield token
            elif provider.provider_type == "anthropic":
                async for token in self._stream_anthropic(messages, system_prompt, provider, resolved_model, temperature):
                    yield token
            else:
                yield f"Error: Streaming not supported for provider: {provider.provider_type}"

    async def _stream_openai(
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
                base_url=provider.base_url or None,
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

    async def generate_with_context(
        self,
        prompt: str,
        context: List[Dict[str, Any]],
        provider_type: Optional[str] = None,
    ) -> str:
        context_str = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in context
        ])
        
        full_prompt = f"""Context:
{context_str}

Current question: {prompt}"""
        
        return await self.generate(full_prompt, provider_type)


llm_service = LLMService()
