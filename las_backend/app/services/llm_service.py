from typing import Optional, List, Dict, Any
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
            
            if provider.provider_type == "openai":
                return await self._generate_openai(prompt, provider, model_id or "gpt-4o-mini")
            elif provider.provider_type == "anthropic":
                return await self._generate_anthropic(prompt, provider, model_id or "claude-3-5-sonnet-20241022")
            elif provider.provider_type == "ollama":
                return await self._generate_ollama(prompt, provider, model_id or "llama2")
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
