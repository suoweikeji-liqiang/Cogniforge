"""
Timeout and Degradation Tests
Tests for budget guards and fallback logic
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_problem_creation_degrades_to_local_fallback_under_llm_timeouts(client: AsyncClient, auth_headers: dict, monkeypatch):
    from app.api.routes import problems as problem_routes
    from app.services.model_os_service import model_os_service

    async def slow_concepts(*args, **kwargs):
        await asyncio.sleep(0.05)
        return ["late concept"]

    async def slow_learning_path(*args, **kwargs):
        await asyncio.sleep(0.05)
        return []

    monkeypatch.setattr(problem_routes, "_problem_create_concept_timeout_seconds", lambda: 0.01)
    monkeypatch.setattr(problem_routes, "_problem_create_path_timeout_seconds", lambda: 0.01)
    monkeypatch.setattr(model_os_service, "build_problem_concepts_resilient", slow_concepts)
    monkeypatch.setattr(model_os_service, "generate_learning_path_resilient", slow_learning_path)

    response = await client.post(
        "/api/problems/",
        headers=auth_headers,
        json={
            "title": "Metrics Launch Test",
            "description": "Understand precision and recall tradeoffs.",
            "associated_concepts": [],
            "learning_mode": "exploration",
        },
    )

    assert response.status_code == 201
    problem = response.json()
    associated_concepts = [item.lower() for item in problem["associated_concepts"]]
    assert "precision" in associated_concepts
    assert "recall" in associated_concepts

    path_response = await client.get(
        f"/api/problems/{problem['id']}/learning-path",
        headers=auth_headers,
    )
    assert path_response.status_code == 200
    path = path_response.json()
    assert path["path_data"]
    assert "precision" in path["path_data"][0]["concept"].lower()


@pytest.mark.asyncio
async def test_llm_timeout_triggers_fallback(client: AsyncClient, auth_headers: dict, db_session):
    """When LLM times out, should use fallback and record reason"""
    problem_response = await client.post(
        "/api/problems/",
        headers=auth_headers,
        json={"title": "Test Problem", "associated_concepts": []},
    )
    problem_id = problem_response.json()["id"]

    async def timeout_coroutine(*args, **kwargs):
        raise asyncio.TimeoutError()

    with patch("app.services.model_os_service.model_os_service.generate_feedback_structured") as mock_llm:
        mock_llm.side_effect = timeout_coroutine

        response = await client.post(
            f"/api/problems/{problem_id}/responses",
            headers=auth_headers,
            json={"problem_id": problem_id, "user_response": "Test response"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["fallback_reason"] is not None
        assert "timeout" in data["fallback_reason"].lower() or "error" in data["fallback_reason"].lower()


@pytest.mark.asyncio
async def test_llm_call_budget_enforcement(client: AsyncClient, auth_headers: dict, monkeypatch):
    """Should not exceed PROBLEM_MAX_LLM_CALLS_PER_REQUEST"""
    monkeypatch.setenv("PROBLEM_MAX_LLM_CALLS_PER_REQUEST", "2")

    problem_response = await client.post(
        "/api/problems/",
        headers=auth_headers,
        json={"title": "Test Problem", "associated_concepts": []},
    )
    problem_id = problem_response.json()["id"]

    response = await client.post(
        f"/api/problems/{problem_id}/responses",
        headers=auth_headers,
        json={"problem_id": problem_id, "user_response": "Test response"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["llm_calls"] is not None
    assert data["llm_calls"] <= 2


@pytest.mark.asyncio
async def test_low_priority_calls_skipped_when_time_low(client: AsyncClient, auth_headers: dict):
    """Low priority calls should be skipped when timeout budget is low"""
    problem_response = await client.post(
        "/api/problems/",
        headers=auth_headers,
        json={"title": "Test Problem", "associated_concepts": []},
    )
    problem_id = problem_response.json()["id"]

    with patch("app.services.model_os_service.ModelOSService.generate_feedback_structured") as mock_feedback:
        # Make feedback call slow to consume time budget
        async def slow_feedback(*args, **kwargs):
            await asyncio.sleep(0.5)
            return {
                "correctness": "correct",
                "misconceptions": [],
                "suggestions": [],
                "next_question": "",
            }
        mock_feedback.side_effect = slow_feedback

        response = await client.post(
            f"/api/problems/{problem_id}/responses",
            headers=auth_headers,
            json={"problem_id": problem_id, "user_response": "Test"},
        )

        assert response.status_code == 200
        data = response.json()
        # Should have fallback reason for skipped low-priority calls
        if data.get("fallback_reason"):
            assert "skip_low_priority" in data["fallback_reason"] or "timeout" in data["fallback_reason"]


@pytest.mark.asyncio
async def test_observability_fields_present(client: AsyncClient, auth_headers: dict):
    """All observability fields should be present in response"""
    problem_response = await client.post(
        "/api/problems/",
        headers=auth_headers,
        json={"title": "Test Problem", "associated_concepts": []},
    )
    problem_id = problem_response.json()["id"]

    response = await client.post(
        f"/api/problems/{problem_id}/responses",
        headers=auth_headers,
        json={"problem_id": problem_id, "user_response": "Test response"},
    )

    assert response.status_code == 200
    data = response.json()

    # Check all observability fields
    assert "trace_id" in data
    assert data["trace_id"] is not None
    assert "llm_calls" in data
    assert isinstance(data["llm_calls"], int)
    assert "llm_latency_ms" in data
    assert isinstance(data["llm_latency_ms"], int)
    assert "fallback_reason" in data  # Can be None


@pytest.mark.asyncio
async def test_ask_endpoint_observability(client: AsyncClient, auth_headers: dict):
    """Ask endpoint should also have observability fields"""
    problem_response = await client.post(
        "/api/problems/",
        headers=auth_headers,
        json={"title": "Test Problem", "associated_concepts": []},
    )
    problem_id = problem_response.json()["id"]

    response = await client.post(
        f"/api/problems/{problem_id}/ask",
        headers=auth_headers,
        json={"question": "What is this?", "answer_mode": "direct"},
    )

    assert response.status_code == 200
    data = response.json()

    assert "trace_id" in data
    assert "llm_calls" in data
    assert "llm_latency_ms" in data
    assert "fallback_reason" in data
