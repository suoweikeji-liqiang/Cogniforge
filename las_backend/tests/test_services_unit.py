"""
Service Layer Unit Tests
Tests core business logic with real LLM integration
"""

import pytest
import os
import asyncio
import time
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_model_os_extract_concepts():
    """Test concept extraction logic"""
    from app.services.model_os_service import model_os_service

    concepts = await model_os_service.extract_related_concepts_resilient(
        problem_title="向量检索",
        problem_description="我需要理解向量检索和语义搜索的原理",
        limit=5
    )

    assert isinstance(concepts, list)
    assert len(concepts) <= 5


def test_model_os_rank_model_cards_prefers_direct_match():
    from app.services.model_os_service import model_os_service

    now = datetime.utcnow()
    direct = type(
        "Card",
        (),
        {
            "title": "Vector Threshold Tradeoff",
            "user_notes": "precision recall threshold boundary",
            "examples": ["threshold sweep"],
            "counter_examples": [],
            "embedding": None,
            "updated_at": now,
            "created_at": now,
        },
    )()
    partial = type(
        "Card",
        (),
        {
            "title": "Threshold Notes",
            "user_notes": "decision boundary",
            "examples": ["comparison"],
            "counter_examples": [],
            "embedding": None,
            "updated_at": now - timedelta(minutes=1),
            "created_at": now - timedelta(minutes=1),
        },
    )()
    unrelated = type(
        "Card",
        (),
        {
            "title": "SQL Basics",
            "user_notes": "joins and filters",
            "examples": ["select"],
            "counter_examples": [],
            "embedding": None,
            "updated_at": now - timedelta(minutes=2),
            "created_at": now - timedelta(minutes=2),
        },
    )()

    ranked = model_os_service.rank_model_cards(
        [unrelated, partial, direct],
        "vector threshold",
    )

    assert ranked[0].title == "Vector Threshold Tradeoff"
    assert any(card.title == "Threshold Notes" for card in ranked)
    assert all(card.title != "SQL Basics" for card in ranked)


@pytest.mark.asyncio
async def test_srs_service_schedule_calculation():
    """Test SRS interval calculation"""
    from app.services.srs_service import SRSService
    from app.models.entities.user import ReviewSchedule
    from datetime import datetime

    srs = SRSService()

    # Create initial schedule
    schedule = ReviewSchedule(
        user_id="test",
        model_card_id="test",
        ease_factor=2500,
        interval_days=1,
        repetitions=0,
        next_review_at=datetime.utcnow()
    )

    # First review with quality 5
    srs.process_review(schedule, quality=5)
    assert schedule.interval_days == 1
    assert schedule.repetitions == 1
    assert schedule.ease_factor >= 2500

    # Second review with quality 4
    srs.process_review(schedule, quality=4)
    assert schedule.interval_days == 6
    assert schedule.repetitions == 2


@pytest.mark.asyncio
async def test_model_os_feedback_structure():
    """Test feedback generation returns correct structure"""
    from app.services.model_os_service import model_os_service

    feedback = await model_os_service.generate_feedback_structured(
        user_response="向量检索使用余弦相似度",
        concept="向量检索",
        model_examples=["embedding", "similarity"]
    )

    assert "correctness" in feedback
    assert "suggestions" in feedback
    assert feedback["correctness"] in ["correct", "partially correct", "incorrect"]


@pytest.mark.asyncio
async def test_llm_service_generate_respects_wait_for_with_blocking_provider(monkeypatch):
    from app.services.llm_service import LLMService, llm_service
    import openai

    provider = type(
        "Provider",
        (),
        {
            "name": "Blocking Qwen",
            "provider_type": "qwen",
            "api_key": "super-secret-key",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "enabled": True,
            "priority": 100,
            "id": 1,
        },
    )()
    default_model = type("Model", (), {"model_id": "qwen-plus"})()

    class SlowOpenAI:
        def __init__(self, api_key, base_url=None):
            self.chat = self
            self.completions = self

        def create(self, model, messages, temperature, timeout):
            time.sleep(0.2)
            message = type("Message", (), {"content": "late"})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    async def fake_get_active_provider(db, provider_type=None):
        return provider

    async def fake_get_default_model(db, provider_id):
        return default_model

    # tests/conftest.py autouse-stubs model_os_service.llm.generate; restore the real
    # implementation here so this regression actually exercises wait_for cancellation.
    monkeypatch.setattr(llm_service, "generate", LLMService.generate.__get__(llm_service, LLMService))
    monkeypatch.setattr(openai, "OpenAI", SlowOpenAI)
    monkeypatch.setattr(llm_service, "_get_active_provider", fake_get_active_provider)
    monkeypatch.setattr(llm_service, "_get_default_model", fake_get_default_model)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(llm_service.generate("hello", provider_type="qwen"), timeout=0.01)


@pytest.mark.asyncio
async def test_llm_service_generate_structured_json_uses_openai_json_schema(monkeypatch):
    from app.services.llm_service import LLMService, llm_service
    import openai

    provider = type(
        "Provider",
        (),
        {
            "name": "Structured Qwen",
            "provider_type": "qwen",
            "api_key": "super-secret-key",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "enabled": True,
            "priority": 100,
            "id": 1,
        },
    )()
    default_model = type("Model", (), {"model_id": "qwen-plus"})()

    class StructuredOpenAI:
        def __init__(self, api_key, base_url=None):
            self.chat = self
            self.completions = self

        def create(self, model, messages, temperature, response_format, timeout):
            assert model == "qwen-plus"
            assert temperature == 0
            assert response_format["type"] == "json_schema"
            assert response_format["json_schema"]["name"] == "structured_feedback"
            assert response_format["json_schema"]["schema"]["type"] == "object"
            message = type("Message", (), {"content": '{"correctness":"correct"}'})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    async def fake_get_active_provider(db, provider_type=None):
        return provider

    async def fake_get_default_model(db, provider_id):
        return default_model

    monkeypatch.setattr(llm_service, "generate_structured_json", LLMService.generate_structured_json.__get__(llm_service, LLMService))
    monkeypatch.setattr(openai, "OpenAI", StructuredOpenAI)
    monkeypatch.setattr(llm_service, "_get_active_provider", fake_get_active_provider)
    monkeypatch.setattr(llm_service, "_get_default_model", fake_get_default_model)

    result = await llm_service.generate_structured_json(
        "Return structured feedback",
        {"type": "object", "properties": {"correctness": {"type": "string"}}, "required": ["correctness"]},
        schema_name="structured_feedback",
        provider_type="qwen",
    )

    assert result == {"correctness": "correct"}
