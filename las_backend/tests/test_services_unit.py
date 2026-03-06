"""
Service Layer Unit Tests
Tests core business logic with real LLM integration
"""

import pytest
import os


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
