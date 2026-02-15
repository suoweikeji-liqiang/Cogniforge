from typing import Optional, List, Dict, Any
import openai
from app.core.config import get_settings

settings = get_settings()


class LLMService:
    def __init__(self):
        self.default_provider = settings.DEFAULT_LLM_PROVIDER
        openai.api_key = settings.OPENAI_API_KEY
    
    async def generate(
        self,
        prompt: str,
        provider: Optional[str] = None,
        **kwargs
    ) -> str:
        provider = provider or self.default_provider
        
        if provider == "openai":
            return await self._generate_openai(prompt)
        elif provider == "anthropic":
            return await self._generate_anthropic(prompt)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def _generate_openai(self, prompt: str) -> str:
        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    async def _generate_anthropic(self, prompt: str) -> str:
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            response = client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    async def generate_with_context(
        self,
        prompt: str,
        context: List[Dict[str, Any]],
        provider: Optional[str] = None,
    ) -> str:
        context_str = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in context
        ])
        
        full_prompt = f"""Context:
{context_str}

Current question: {prompt}"""
        
        return await self.generate(full_prompt, provider)


llm_service = LLMService()
