import pytest
from sqlalchemy import select


async def register_and_login(client):
    register_payload = {
        "email": "user@example.com",
        "username": "tester",
        "password": "secret123",
        "full_name": "Test User",
    }
    register_response = await client.post("/api/auth/register", json=register_payload)
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/auth/login",
        data={"username": "tester", "password": "secret123"},
    )
    assert login_response.status_code == 200
    return login_response.json()


async def create_problem(client, headers, title="Learning Loop", description="Need better mastery signals"):
    response = await client.post(
        "/api/problems/",
        json={
            "title": title,
            "description": description,
            "associated_concepts": ["feedback loop"],
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_problem_response_records_mastery_and_events(client, db_session):
    from app.models.entities.user import LearningEvent, ProblemMasteryEvent

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers)

    response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={"problem_id": problem["id"], "user_response": "I think I understand the basics."},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["learning_mode"] == "socratic"
    assert body["mode_metadata"]["turn_source"] == "response"
    assert body["trace_id"]
    assert body["llm_calls"] >= 1
    assert "mastery_score" in body["structured_feedback"]
    assert "confidence" in body["structured_feedback"]
    assert "decision_reason" in body["structured_feedback"]

    mastery_result = await db_session.execute(
        select(ProblemMasteryEvent).where(ProblemMasteryEvent.problem_id == problem["id"])
    )
    mastery_events = mastery_result.scalars().all()
    assert len(mastery_events) == 1
    assert mastery_events[0].mastery_score >= 0

    event_result = await db_session.execute(
        select(LearningEvent).where(
            LearningEvent.problem_id == problem["id"],
            LearningEvent.event_type == "problem_response_evaluated",
        )
    )
    event = event_result.scalar_one_or_none()
    assert event is not None
    assert event.learning_mode == "socratic"


@pytest.mark.asyncio
async def test_problem_learning_mode_switch_persists_and_turns_are_listed(client, db_session):
    from app.models.entities.user import ProblemTurn

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Mode switch")

    update_response = await client.put(
        f"/api/problems/{problem['id']}",
        json={"learning_mode": "exploration"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["learning_mode"] == "exploration"

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "What concept should I study next?",
            "learning_mode": "exploration",
            "answer_mode": "guided",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    ask_body = ask_response.json()
    assert ask_body["learning_mode"] == "exploration"
    assert ask_body["mode_metadata"]["turn_source"] == "ask"

    response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={
            "problem_id": problem["id"],
            "user_response": "Here is my attempted answer.",
            "learning_mode": "socratic",
        },
        headers=headers,
    )
    assert response.status_code == 200
    response_body = response.json()
    assert response_body["learning_mode"] == "socratic"

    turns_response = await client.get(
        f"/api/problems/{problem['id']}/turns",
        headers=headers,
    )
    assert turns_response.status_code == 200
    turns = turns_response.json()
    assert len(turns) >= 2
    assert any(item["learning_mode"] == "exploration" for item in turns)
    assert any(item["learning_mode"] == "socratic" for item in turns)

    exploration_turns = await client.get(
        f"/api/problems/{problem['id']}/turns",
        params={"learning_mode": "exploration"},
        headers=headers,
    )
    assert exploration_turns.status_code == 200
    assert all(item["learning_mode"] == "exploration" for item in exploration_turns.json())

    turn_rows = await db_session.execute(
        select(ProblemTurn).where(ProblemTurn.problem_id == problem["id"])
    )
    stored_turns = turn_rows.scalars().all()
    assert len(stored_turns) >= 2
    assert any(turn.learning_mode == "exploration" for turn in stored_turns)
    assert any(turn.learning_mode == "socratic" for turn in stored_turns)


@pytest.mark.asyncio
async def test_learning_step_hint_still_works_after_mode_switch(client):
    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Hint mode switch")

    update_response = await client.put(
        f"/api/problems/{problem['id']}",
        json={"learning_mode": "exploration"},
        headers=headers,
    )
    assert update_response.status_code == 200

    hint_response = await client.get(
        f"/api/problems/{problem['id']}/learning-path/hint",
        headers=headers,
    )
    assert hint_response.status_code == 200
    hint_body = hint_response.json()
    assert "step_index" in hint_body
    assert "structured_hint" in hint_body


@pytest.mark.asyncio
async def test_problem_auto_advance_v2_requires_streak(client, monkeypatch):
    from app.api.routes import problems as problems_route
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Streak test")

    async def fake_feedback(*args, **kwargs):
        return {
            "correctness": "correct",
            "misconceptions": [],
            "suggestions": ["solid reasoning"],
            "next_question": "What would fail first?",
            "mastery_score": 90,
            "dimension_scores": {"accuracy": 90, "completeness": 88, "transfer": 86, "rigor": 89},
            "confidence": 0.91,
            "pass_stage": True,
            "decision_reason": "Strong answer",
        }

    monkeypatch.setattr(model_os_service, "generate_feedback_structured", fake_feedback)

    previous_v2 = problems_route.settings.PROBLEM_AUTO_ADVANCE_V2_ENABLED
    previous_mode = problems_route.settings.PROBLEM_AUTO_ADVANCE_MODE
    problems_route.settings.PROBLEM_AUTO_ADVANCE_V2_ENABLED = True
    problems_route.settings.PROBLEM_AUTO_ADVANCE_MODE = "balanced"
    try:
        first = await client.post(
            f"/api/problems/{problem['id']}/responses",
            json={"problem_id": problem["id"], "user_response": "First pass response."},
            headers=headers,
        )
        assert first.status_code == 200
        assert first.json()["auto_advanced"] is False

        second = await client.post(
            f"/api/problems/{problem['id']}/responses",
            json={"problem_id": problem["id"], "user_response": "Second pass response."},
            headers=headers,
        )
        assert second.status_code == 200
        assert second.json()["auto_advanced"] is True
        assert second.json()["new_current_step"] == 1
    finally:
        problems_route.settings.PROBLEM_AUTO_ADVANCE_V2_ENABLED = previous_v2
        problems_route.settings.PROBLEM_AUTO_ADVANCE_MODE = previous_mode


@pytest.mark.asyncio
async def test_problem_concept_candidates_accept_and_rollback(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Candidate flow")

    async def fake_extract(*args, **kwargs):
        return ["Noisy Concept"]

    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    create_response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={"problem_id": problem["id"], "user_response": "I need more clarity."},
        headers=headers,
    )
    assert create_response.status_code == 200
    body = create_response.json()
    assert "Noisy Concept" in body["pending_concepts"]

    candidates_response = await client.get(
        f"/api/problems/{problem['id']}/concept-candidates",
        headers=headers,
    )
    assert candidates_response.status_code == 200
    candidates = candidates_response.json()
    assert candidates
    candidate = next((item for item in candidates if item["concept_text"] == "Noisy Concept"), None)
    assert candidate is not None
    assert candidate["status"] == "pending"

    accept_response = await client.post(
        f"/api/problems/{problem['id']}/concept-candidates/{candidate['id']}/accept",
        headers=headers,
    )
    assert accept_response.status_code == 200
    accepted_payload = accept_response.json()
    assert accepted_payload["candidate"]["status"] == "accepted"

    problem_after_accept = await client.get(f"/api/problems/{problem['id']}", headers=headers)
    assert problem_after_accept.status_code == 200
    assert "Noisy Concept" in problem_after_accept.json()["associated_concepts"]

    rollback_response = await client.post(
        f"/api/problems/{problem['id']}/concepts/rollback",
        json={"concept_text": "Noisy Concept", "reason": "irrelevant"},
        headers=headers,
    )
    assert rollback_response.status_code == 200
    assert rollback_response.json()["removed"] is True

    problem_after_rollback = await client.get(f"/api/problems/{problem['id']}", headers=headers)
    assert problem_after_rollback.status_code == 200
    assert "Noisy Concept" not in problem_after_rollback.json()["associated_concepts"]


@pytest.mark.asyncio
async def test_problem_ask_updates_candidates_and_logs_event(client, db_session, monkeypatch):
    from app.models.entities.user import LearningEvent
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Ask flow")

    async def fake_extract(*args, **kwargs):
        return ["Clarifying Question Pattern"]

    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={"question": "How do I validate this quickly?", "answer_mode": "guided"},
        headers=headers,
    )
    assert ask_response.status_code == 200
    ask_body = ask_response.json()
    assert ask_body["learning_mode"] == "exploration"
    assert ask_body["mode_metadata"]["turn_source"] == "ask"
    assert ask_body["trace_id"]
    assert ask_body["llm_calls"] >= 1
    assert "suggested_next_focus" in ask_body
    assert (
        "Clarifying Question Pattern" in ask_body["pending_concepts"]
        or "Clarifying Question Pattern" in ask_body["accepted_concepts"]
    )

    events_result = await db_session.execute(
        select(LearningEvent).where(
            LearningEvent.problem_id == problem["id"],
            LearningEvent.event_type == "problem_inline_qa",
        )
    )
    event = events_result.scalar_one_or_none()
    assert event is not None
    assert event.learning_mode == "exploration"

    candidates_response = await client.get(
        f"/api/problems/{problem['id']}/concept-candidates",
        params={"status": "pending"},
        headers=headers,
    )
    assert candidates_response.status_code == 200
    assert any(
        item["source"] == "ask"
        and item["learning_mode"] == "exploration"
        and item["source_turn_id"] is not None
        for item in candidates_response.json()
    )


@pytest.mark.asyncio
async def test_problem_response_budget_guard_skips_low_priority_calls(client, monkeypatch):
    from app.api.routes import problems as problems_route
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Budget guard")

    async def fake_feedback(*args, **kwargs):
        return {
            "correctness": "partially correct",
            "misconceptions": [],
            "suggestions": ["add one edge case"],
            "next_question": "Which assumption can break?",
            "mastery_score": 70,
            "dimension_scores": {"accuracy": 70, "completeness": 68, "transfer": 66, "rigor": 65},
            "confidence": 0.7,
            "pass_stage": False,
            "decision_reason": "Needs one more iteration",
        }

    async def fake_extract(*args, **kwargs):
        return ["Should Not Run"]

    monkeypatch.setattr(model_os_service, "generate_feedback_structured", fake_feedback)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    previous_budget = problems_route.settings.PROBLEM_MAX_LLM_CALLS_PER_REQUEST
    problems_route.settings.PROBLEM_MAX_LLM_CALLS_PER_REQUEST = 1
    try:
        response = await client.post(
            f"/api/problems/{problem['id']}/responses",
            json={"problem_id": problem["id"], "user_response": "Budget-limited response"},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["llm_calls"] == 1
        assert "budget_exceeded:concept_extraction" in (body.get("fallback_reason") or "")
        assert "Should Not Run" not in body["accepted_concepts"]
    finally:
        problems_route.settings.PROBLEM_MAX_LLM_CALLS_PER_REQUEST = previous_budget
