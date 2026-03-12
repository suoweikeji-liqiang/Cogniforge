import pytest

from app.core.database import AsyncSessionLocal
from app.models.entities.llm_provider import LLMProvider, LLMModel
from app.models.entities.system_settings import SystemSettings
from app.services.model_os_service import LLM_TASK_ROUTES_KEY, ModelOSService


@pytest.mark.asyncio
async def test_generate_with_context_uses_interactive_route(monkeypatch):
    service = ModelOSService()
    monkeypatch.setattr(service.settings, "LLM_INTERACTIVE_PROVIDER_TYPE", "openai")
    monkeypatch.setattr(service.settings, "LLM_INTERACTIVE_MODEL_ID", "gemini-interactive")

    seen = {}

    async def fake_generate_with_context(
        prompt,
        context,
        retrieval_context=None,
        provider_type=None,
        provider_id=None,
        model_id=None,
    ):
        seen["provider_id"] = provider_id
        seen["provider_type"] = provider_type
        seen["model_id"] = model_id
        return "interactive answer"

    monkeypatch.setattr(service.llm, "generate_with_context", fake_generate_with_context)

    result = await service.generate_with_context(
        prompt="What is recall?",
        context=[{"role": "assistant", "content": "Previous turn"}],
    )

    assert result == "interactive answer"
    assert seen == {
        "provider_id": None,
        "provider_type": "openai",
        "model_id": "gemini-interactive",
    }


@pytest.mark.asyncio
async def test_stream_generate_with_context_uses_interactive_route(monkeypatch):
    service = ModelOSService()
    monkeypatch.setattr(service.settings, "LLM_INTERACTIVE_PROVIDER_TYPE", "openai")
    monkeypatch.setattr(service.settings, "LLM_INTERACTIVE_MODEL_ID", "gemini-interactive")

    seen = {}

    async def fake_stream_generate_with_context(
        prompt,
        context,
        retrieval_context=None,
        provider_type=None,
        provider_id=None,
        model_id=None,
        temperature=0.7,
    ):
        seen["provider_id"] = provider_id
        seen["provider_type"] = provider_type
        seen["model_id"] = model_id
        yield "token-1"
        yield "token-2"

    monkeypatch.setattr(service.llm, "stream_generate_with_context", fake_stream_generate_with_context)

    tokens = [
        token
        async for token in service.stream_generate_with_context(
            prompt="Explain precision.",
            context=[],
        )
    ]

    assert tokens == ["token-1", "token-2"]
    assert seen == {
        "provider_id": None,
        "provider_type": "openai",
        "model_id": "gemini-interactive",
    }


@pytest.mark.asyncio
async def test_generate_text_for_lane_retries_configured_fallback_route(monkeypatch):
    service = ModelOSService()
    monkeypatch.setattr(service.settings, "LLM_INTERACTIVE_PROVIDER_TYPE", "openai")
    monkeypatch.setattr(service.settings, "LLM_INTERACTIVE_MODEL_ID", "gemini-interactive")
    monkeypatch.setattr(service.settings, "LLM_FALLBACK_PROVIDER_TYPE", "qwen")
    monkeypatch.setattr(service.settings, "LLM_FALLBACK_MODEL_ID", "deepseek-fallback")

    calls = []

    async def fake_generate(prompt, provider_type=None, model_id=None, **kwargs):
        calls.append((provider_type, model_id))
        if len(calls) == 1:
            return "Error: upstream timeout"
        return "fallback answer"

    monkeypatch.setattr(service.llm, "generate", fake_generate)

    result = await service.generate_text_for_lane("Explain recall.", lane="interactive")

    assert result == "fallback answer"
    assert calls == [
        ("openai", "gemini-interactive"),
        ("qwen", "deepseek-fallback"),
    ]


@pytest.mark.asyncio
async def test_generate_feedback_structured_uses_interactive_route_then_fallback(monkeypatch):
    service = ModelOSService()
    monkeypatch.setattr(service.settings, "LLM_INTERACTIVE_PROVIDER_TYPE", "openai")
    monkeypatch.setattr(service.settings, "LLM_INTERACTIVE_MODEL_ID", "gemini-interactive")
    monkeypatch.setattr(service.settings, "LLM_FALLBACK_PROVIDER_TYPE", "qwen")
    monkeypatch.setattr(service.settings, "LLM_FALLBACK_MODEL_ID", "deepseek-fallback")

    structured_calls = []

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        structured_calls.append((kwargs.get("provider_type"), kwargs.get("model_id"), kwargs.get("schema_name")))
        if len(structured_calls) == 1:
            return None
        return {
            "correctness": "correct",
            "misconceptions": [],
            "suggestions": ["Good boundary explanation."],
            "next_question": "What changes when prevalence shifts?",
            "mastery_score": 88,
            "dimension_scores": {"accuracy": 88, "completeness": 87, "transfer": 89, "rigor": 88},
            "confidence": 0.84,
            "pass_stage": True,
            "decision_reason": "Fallback model produced valid structured output",
        }

    async def should_not_run(prompt, **kwargs):
        raise AssertionError("text fallback should not run when fallback structured route succeeds")

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", should_not_run)

    feedback = await service.generate_feedback_structured(
        user_response="Lowering the threshold increases recall.",
        concept="Precision-recall tradeoff",
        model_examples=["precision", "recall"],
    )

    assert feedback["pass_stage"] is True
    assert structured_calls == [
        ("openai", "gemini-interactive", "structured_feedback"),
        ("qwen", "deepseek-fallback", "structured_feedback"),
    ]


@pytest.mark.asyncio
async def test_generate_learning_path_uses_structured_heavy_route(monkeypatch):
    service = ModelOSService()
    monkeypatch.setattr(service.settings, "LLM_STRUCTURED_HEAVY_PROVIDER_TYPE", "qwen")
    monkeypatch.setattr(service.settings, "LLM_STRUCTURED_HEAVY_MODEL_ID", "deepseek-structured")

    seen = {}

    async def fake_generate_structured_json(prompt, json_schema, **kwargs):
        seen["provider_type"] = kwargs.get("provider_type")
        seen["model_id"] = kwargs.get("model_id")
        seen["schema_name"] = kwargs.get("schema_name")
        return [
            {
                "step": 1,
                "concept": "Precision",
                "description": "Define precision in a defect triage workflow.",
                "resources": ["false positives", "triage"],
            }
        ]

    async def should_not_run(prompt, **kwargs):
        raise AssertionError("text fallback should not run when structured-heavy route succeeds")

    monkeypatch.setattr(service.llm, "generate_structured_json", fake_generate_structured_json)
    monkeypatch.setattr(service.llm, "generate", should_not_run)

    path = await service.generate_learning_path(
        problem_title="Threshold tuning",
        problem_description="Understand the precision-recall tradeoff in deployment.",
        existing_knowledge=["binary classification"],
        associated_concepts=["precision", "recall"],
    )

    assert len(path) == 1
    assert seen == {
        "provider_type": "qwen",
        "model_id": "deepseek-structured",
        "schema_name": "learning_path",
    }


@pytest.mark.asyncio
async def test_db_task_route_overrides_env_route(monkeypatch):
    service = ModelOSService()
    monkeypatch.setattr(service.settings, "LLM_INTERACTIVE_PROVIDER_TYPE", "openai")
    monkeypatch.setattr(service.settings, "LLM_INTERACTIVE_MODEL_ID", "gemini-interactive")

    async with AsyncSessionLocal() as db:
        provider = LLMProvider(
            name="DashScope",
            provider_type="qwen",
            api_key="test-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            enabled=True,
            priority=5,
        )
        db.add(provider)
        await db.flush()

        model = LLMModel(
            provider_id=provider.id,
            model_id="deepseek-v3.2",
            model_name="DeepSeek V3.2",
            enabled=True,
            is_default=True,
        )
        db.add(model)
        await db.flush()

        db.add(
            SystemSettings(
                key=LLM_TASK_ROUTES_KEY,
                value={
                    "interactive": {"provider_id": provider.id, "model_record_id": model.id},
                    "structured_heavy": {"provider_id": None, "model_record_id": None},
                    "fallback": {"provider_id": None, "model_record_id": None},
                },
                description="test llm task routes",
            )
        )
        await db.commit()

    seen = {}

    async def fake_generate_with_context(
        prompt,
        context,
        retrieval_context=None,
        provider_type=None,
        provider_id=None,
        model_id=None,
    ):
        seen["provider_id"] = provider_id
        seen["provider_type"] = provider_type
        seen["model_id"] = model_id
        return "db-routed answer"

    monkeypatch.setattr(service.llm, "generate_with_context", fake_generate_with_context)

    result = await service.generate_with_context(
        prompt="Explain false positives.",
        context=[],
    )

    assert result == "db-routed answer"
    assert seen == {
        "provider_id": provider.id,
        "provider_type": "qwen",
        "model_id": "deepseek-v3.2",
    }
