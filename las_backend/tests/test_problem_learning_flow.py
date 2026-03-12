import json
import asyncio

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
async def test_problem_creation_fallback_learning_path_prioritizes_associated_concepts(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    async def failing_learning_path(*args, **kwargs):
        raise RuntimeError("force fallback")

    async def fixed_problem_concepts(*args, **kwargs):
        return ["precision", "recall"]

    monkeypatch.setattr(model_os_service, "generate_learning_path", failing_learning_path)
    monkeypatch.setattr(model_os_service, "build_problem_concepts_resilient", fixed_problem_concepts)

    create_response = await client.post(
        "/api/problems/",
        json={
            "title": "Real Metrics Test",
            "description": "Understand precision, recall, and threshold tradeoffs.",
            "associated_concepts": ["precision", "recall"],
            "learning_mode": "exploration",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    problem = create_response.json()

    path_response = await client.get(
        f"/api/problems/{problem['id']}/learning-path",
        headers=headers,
    )
    assert path_response.status_code == 200
    body = path_response.json()
    first_step = body["path_data"][0]
    second_step = body["path_data"][1]

    assert "clarify goal and constraints" not in first_step["concept"].lower()
    assert "precision" in first_step["concept"].lower()
    assert "recall" in first_step["concept"].lower()
    assert "precision" in first_step["description"].lower()
    assert "recall" in first_step["description"].lower()
    assert "precision" in second_step["concept"].lower()
    assert "recall" in second_step["concept"].lower()


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
async def test_problem_response_persists_core_turn_when_learning_event_logging_fails(
    client,
    db_session,
    monkeypatch,
):
    from app.api.routes import problems as problems_route
    from app.models.entities.user import ProblemMasteryEvent, ProblemResponse as ProblemResponseModel

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers)

    async def failing_log_learning_event(*args, **kwargs):
        raise RuntimeError("learning event store offline")

    monkeypatch.setattr(problems_route, "_log_learning_event", failing_log_learning_event)

    response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={"problem_id": problem["id"], "user_response": "I can explain the core loop."},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "error:learning_event_persist" in (body.get("fallback_reason") or "")

    response_result = await db_session.execute(
        select(ProblemResponseModel).where(ProblemResponseModel.problem_id == problem["id"])
    )
    stored_responses = response_result.scalars().all()
    assert len(stored_responses) == 1
    assert stored_responses[0].user_response == "I can explain the core loop."

    mastery_result = await db_session.execute(
        select(ProblemMasteryEvent).where(ProblemMasteryEvent.problem_id == problem["id"])
    )
    assert mastery_result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_problem_response_clamps_long_correctness_label(client, db_session, monkeypatch):
    from app.models.entities.user import ProblemMasteryEvent
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Long correctness label")

    long_correctness = "correct " + ("very " * 40) + "detailed explanation"

    async def fake_feedback(*args, **kwargs):
        return {
            "correctness": long_correctness,
            "misconceptions": [],
            "suggestions": ["Keep the explanation grounded in one example."],
            "next_question": "What example best validates your claim?",
            "mastery_score": 90,
            "dimension_scores": {"accuracy": 90, "completeness": 88, "transfer": 84, "rigor": 86},
            "confidence": 0.91,
            "pass_stage": True,
            "decision_reason": "Strong answer, but correctness text is intentionally long.",
        }

    monkeypatch.setattr(model_os_service, "generate_feedback_structured", fake_feedback)

    response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={"problem_id": problem["id"], "user_response": "Integral action eliminates steady-state error."},
        headers=headers,
    )
    assert response.status_code == 200

    mastery_result = await db_session.execute(
        select(ProblemMasteryEvent).where(ProblemMasteryEvent.problem_id == problem["id"])
    )
    mastery_event = mastery_result.scalar_one()
    assert mastery_event.correctness_label == long_correctness[:100]


@pytest.mark.asyncio
async def test_problem_response_persists_core_turn_when_concept_candidate_logging_fails(
    client,
    db_session,
    monkeypatch,
):
    from app.api.routes import problems as problems_route
    from app.models.entities.user import ProblemMasteryEvent, ProblemResponse as ProblemResponseModel

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Optional concept candidate failure")

    async def failing_register_problem_concept_candidates(*args, **kwargs):
        raise RuntimeError("concept candidate store offline")

    monkeypatch.setattr(
        problems_route,
        "_register_problem_concept_candidates",
        failing_register_problem_concept_candidates,
    )

    response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={"problem_id": problem["id"], "user_response": "Integral action accumulates residual error over time."},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted_concepts"] == []
    assert body["pending_concepts"] == []
    assert "error:concept_candidate_persist" in (body.get("fallback_reason") or "")

    response_result = await db_session.execute(
        select(ProblemResponseModel).where(ProblemResponseModel.problem_id == problem["id"])
    )
    assert response_result.scalar_one_or_none() is not None

    mastery_result = await db_session.execute(
        select(ProblemMasteryEvent).where(ProblemMasteryEvent.problem_id == problem["id"])
    )
    assert mastery_result.scalar_one_or_none() is not None


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
async def test_problem_ask_persists_turn_when_path_candidate_persistence_fails(
    client,
    db_session,
    monkeypatch,
):
    from app.api.routes import problems as problems_route
    from app.models.entities.user import ProblemTurn

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Optional path candidate failure")

    async def failing_register_problem_path_candidates(*args, **kwargs):
        raise RuntimeError("path candidate store offline")

    monkeypatch.setattr(
        problems_route,
        "register_problem_path_candidates",
        failing_register_problem_path_candidates,
    )

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "PID 中积分项为什么能消除稳态误差？",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["learning_mode"] == "exploration"
    assert body["turn_id"]
    assert body["derived_path_candidates"] == []
    assert "error:path_candidate_persist" in (body.get("fallback_reason") or "")

    turn_rows = await db_session.execute(
        select(ProblemTurn).where(
            ProblemTurn.problem_id == problem["id"],
            ProblemTurn.learning_mode == "exploration",
        )
    )
    assert turn_rows.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_problem_ask_persists_turn_when_concept_candidate_persistence_fails(
    client,
    db_session,
    monkeypatch,
):
    from app.api.routes import problems as problems_route
    from app.models.entities.user import ProblemTurn

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Optional concept candidate failure ask")

    async def failing_register_problem_concept_candidates(*args, **kwargs):
        raise RuntimeError("concept candidate store offline")

    monkeypatch.setattr(
        problems_route,
        "_register_problem_concept_candidates",
        failing_register_problem_concept_candidates,
    )

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "PID 中积分项为什么能消除稳态误差？",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["learning_mode"] == "exploration"
    assert body["turn_id"]
    assert body["accepted_concepts"] == []
    assert body["pending_concepts"] == []
    assert "error:concept_candidate_persist" in (body.get("fallback_reason") or "")

    turn_rows = await db_session.execute(
        select(ProblemTurn).where(
            ProblemTurn.problem_id == problem["id"],
            ProblemTurn.learning_mode == "exploration",
        )
    )
    assert turn_rows.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_problem_ask_sync_route_falls_back_when_answer_is_empty(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(
        client,
        headers,
        title="PID",
        description="理解 PID 控制器中的比例、积分、微分，并说明它们和稳态误差的关系。",
    )

    async def empty_generate_with_context(*args, **kwargs):
        return ""

    monkeypatch.setattr(model_os_service, "generate_with_context", empty_generate_with_context)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "PID 中积分项为什么能消除稳态误差？",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["answer"].startswith("一个简洁的起点：")
    assert "empty:ask_answer" in (body.get("fallback_reason") or "")


@pytest.mark.asyncio
async def test_problem_ask_rewrites_mismatched_answer_language_on_sync_route(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(
        client,
        headers,
        title="Metric tradeoffs",
        description="Understand precision, recall, and threshold tradeoffs.",
    )

    async def fake_answer(*args, **kwargs):
        return (
            "1. **精确率**：预测为正例的样本中，实际为正例的比例。\n"
            "2. **召回率**：实际为正例的样本中，被预测为正例的比例。"
        )

    async def fake_rewrite(*args, **kwargs):
        return (
            "1. **Precision**: the share of predicted positives that are actually positive.\n"
            "2. **Recall**: the share of actual positives that were successfully predicted."
        )

    async def fake_extract(*args, **kwargs):
        return ["precision", "recall"]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service.llm, "generate", fake_rewrite)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "What is the difference between precision and recall?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()

    assert body["answer"].startswith("1. **Precision**")
    assert "精确率" not in body["answer"]
    assert body["llm_calls"] >= 2


@pytest.mark.asyncio
async def test_problem_ask_stream_returns_incremental_answer_and_final_payload(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Accept": "text/event-stream",
    }
    problem = await create_problem(client, headers, title="Streamed exploration")

    async def fake_stream_generate_with_context(*args, **kwargs):
        for token in [
            "Precision measures correct predicted positives. ",
            "Recall measures recovered positives.",
        ]:
            yield token

    monkeypatch.setattr(model_os_service, "stream_generate_with_context", fake_stream_generate_with_context)

    async with client.stream(
        "POST",
        f"/api/problems/{problem['id']}/ask/stream",
        json={
            "question": "What is the difference between precision and recall?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    ) as response:
        assert response.status_code == 200
        body = ""
        async for chunk in response.aiter_text():
            body += chunk

    normalized = body.replace("\r\n", "\n")
    assert "event: token" in normalized
    assert "data: Precision measures correct predicted positives. " in normalized
    assert "event: final" in normalized

    final_blocks = [block for block in normalized.split("\n\n") if "event: final" in block]
    assert final_blocks
    final_data = "\n".join(
        line.removeprefix("data: ")
        for line in final_blocks[-1].splitlines()
        if line.startswith("data: ")
    )
    payload = json.loads(final_data)

    assert payload["learning_mode"] == "exploration"
    assert payload["question"] == "What is the difference between precision and recall?"
    assert payload["answer"].startswith("Precision measures correct predicted positives.")
    assert payload["mode_metadata"]["turn_source"] == "ask"
    assert payload["llm_calls"] >= 1
    assert payload["trace_id"]


@pytest.mark.asyncio
async def test_problem_ask_stream_rewrites_mismatched_answer_language_before_emitting_tokens(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Accept": "text/event-stream",
    }
    problem = await create_problem(client, headers, title="Streamed language alignment")

    async def fake_stream_generate_with_context(*args, **kwargs):
        for token in [
            "1. **精确率**：预测为正例的样本中，实际为正例的比例。",
            "2. **召回率**：实际为正例的样本中，被预测为正例的比例。",
        ]:
            yield token

    async def fake_rewrite(*args, **kwargs):
        return (
            "1. **Precision**: the share of predicted positives that are actually positive.\n"
            "2. **Recall**: the share of actual positives that were successfully predicted."
        )

    monkeypatch.setattr(model_os_service, "stream_generate_with_context", fake_stream_generate_with_context)
    monkeypatch.setattr(model_os_service.llm, "generate", fake_rewrite)

    async with client.stream(
        "POST",
        f"/api/problems/{problem['id']}/ask/stream",
        json={
            "question": "What is the difference between precision and recall?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    ) as response:
        assert response.status_code == 200
        body = ""
        async for chunk in response.aiter_text():
            body += chunk

    normalized = body.replace("\r\n", "\n")
    assert "event: token" in normalized
    assert "data: 1. **Precision**: the share of predicted positives" in normalized
    assert "data: 1. **精确率**" not in normalized

    final_blocks = [block for block in normalized.split("\n\n") if "event: final" in block]
    assert final_blocks
    final_data = "\n".join(
        line.removeprefix("data: ")
        for line in final_blocks[-1].splitlines()
        if line.startswith("data: ")
    )
    payload = json.loads(final_data)
    assert payload["answer"].startswith("1. **Precision**")
    assert "精确率" not in payload["answer"]


@pytest.mark.asyncio
async def test_problem_response_fallback_localizes_pid_follow_up_and_path_candidates(client, monkeypatch):
    from app.api.routes import problem_socratic_response_support as socratic_response_support
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(
        client,
        headers,
        title="PID",
        description="理解 PID 控制器中的比例、积分、微分，并能解释稳态误差为什么出现。",
    )

    async def failing_feedback(*args, **kwargs):
        raise RuntimeError("force structured feedback fallback")

    monkeypatch.setattr(model_os_service, "generate_feedback_structured", failing_feedback)
    monkeypatch.setattr(socratic_response_support.settings, "PROBLEM_AUTO_ADVANCE_MODE", "conservative")

    response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={
            "problem_id": problem["id"],
            "user_response": "我知道积分项会累积误差，但还说不清楚边界。",
            "learning_mode": "socratic",
            "question_kind": "checkpoint",
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["follow_up"]["question"].startswith("如果换一个边界情况")
    assert "正确性：" in (body.get("system_feedback") or "")
    assert body["derived_path_candidates"]
    assert "Fill prerequisite foundations" not in body["derived_path_candidates"][0]["title"]
    assert body["derived_path_candidates"][0]["title"].startswith("先补“")


@pytest.mark.asyncio
async def test_socratic_question_endpoint_returns_probe_by_default(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Question protocol")

    async def fake_generate_question(*args, **kwargs):
        return "What mechanism explains the first step?"

    monkeypatch.setattr(model_os_service, "generate_socratic_question", fake_generate_question)

    response = await client.get(
        f"/api/problems/{problem['id']}/socratic-question",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["learning_mode"] == "socratic"
    assert body["question_kind"] == "probe"
    assert body["question"] == "What mechanism explains the first step?"
    assert body["mode_metadata"]["step_index"] == 0
    assert body["llm_calls"] == 1


@pytest.mark.asyncio
async def test_socratic_question_endpoint_returns_checkpoint_after_mastery_pass(client, db_session, monkeypatch):
    from app.models.entities.user import ProblemMasteryEvent, User
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Checkpoint protocol")

    user_result = await db_session.execute(select(User).where(User.username == "tester"))
    user = user_result.scalar_one()
    db_session.add(
        ProblemMasteryEvent(
            user_id=str(user.id),
            problem_id=problem["id"],
            step_index=0,
            mastery_score=88,
            confidence=0.92,
            pass_stage=True,
            auto_advanced=False,
            correctness_label="correct",
            decision_reason="Checkpoint ready",
        )
    )
    await db_session.commit()

    async def fake_generate_question(*args, **kwargs):
        return "What tradeoff would make you change the threshold?"

    monkeypatch.setattr(model_os_service, "generate_socratic_question", fake_generate_question)

    response = await client.get(
        f"/api/problems/{problem['id']}/socratic-question",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["question_kind"] == "checkpoint"
    assert body["question"] == "What tradeoff would make you change the threshold?"
    assert body["mode_metadata"]["latest_pass_stage"] is True
    assert body["mode_metadata"]["latest_mastery_score"] == 88


@pytest.mark.asyncio
async def test_socratic_question_stream_returns_incremental_question_and_final_payload(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Accept": "text/event-stream",
    }
    problem = await create_problem(client, headers, title="Streamed socratic question")

    async def fake_stream_question(*args, **kwargs):
        for token in ["Why ", "does thresholding matter?"]:
            yield token

    monkeypatch.setattr(model_os_service, "stream_socratic_question", fake_stream_question)

    async with client.stream(
        "GET",
        f"/api/problems/{problem['id']}/socratic-question/stream",
        headers=headers,
    ) as response:
        assert response.status_code == 200
        body = ""
        async for chunk in response.aiter_text():
            body += chunk

    normalized = body.replace("\r\n", "\n")
    assert "event: token" in normalized
    assert "data: Why " in normalized
    assert "data: does thresholding matter?" in normalized
    assert "event: final" in normalized
    assert "event: done" in normalized

    final_blocks = [block for block in normalized.split("\n\n") if "event: final" in block]
    assert final_blocks
    final_data = "\n".join(
        line.removeprefix("data: ")
        for line in final_blocks[-1].splitlines()
        if line.startswith("data: ")
    )
    payload = json.loads(final_data)

    assert payload["learning_mode"] == "socratic"
    assert payload["question_kind"] == "probe"
    assert payload["question"] == "Why does thresholding matter?"
    assert payload["mode_metadata"]["step_index"] == 0
    assert payload["llm_calls"] == 1
    assert payload["trace_id"]


@pytest.mark.asyncio
async def test_socratic_response_stream_returns_status_preview_and_final_payload(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Accept": "text/event-stream",
    }
    problem = await create_problem(client, headers, title="Streamed socratic response")

    async def fake_feedback(*args, **kwargs):
        await asyncio.sleep(0)
        return {
            "correctness": "mostly correct",
            "misconceptions": ["State the threshold tradeoff more explicitly."],
            "suggestions": ["Tie the threshold choice to one concrete cost tradeoff."],
            "next_question": "What boundary case would make you pick a different threshold?",
            "mastery_score": 74,
            "dimension_scores": {"accuracy": 74, "transfer": 70},
            "confidence": 0.78,
            "pass_stage": False,
            "decision_reason": "Still needs a tighter boundary explanation.",
        }

    async def fake_extract_concepts(*args, **kwargs):
        return ["decision threshold", "precision"]

    monkeypatch.setattr(model_os_service, "generate_feedback_structured", fake_feedback)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract_concepts)

    async with client.stream(
        "POST",
        f"/api/problems/{problem['id']}/responses/stream",
        json={
            "problem_id": problem["id"],
            "user_response": "Threshold choice depends on whether false positives or misses are more costly.",
            "learning_mode": "socratic",
            "question_kind": "probe",
            "socratic_question": "Explain the core tradeoff inside threshold choice.",
        },
        headers=headers,
    ) as response:
        assert response.status_code == 200
        body = ""
        async for chunk in response.aiter_text():
            body += chunk

    normalized = body.replace("\r\n", "\n")
    assert "event: status" in normalized
    assert '"phase": "evaluating_feedback"' in normalized
    assert '"phase": "extracting_artifacts"' in normalized
    assert '"phase": "saving_turn"' in normalized
    assert "event: preview" in normalized
    assert '"mastery_score": 74' in normalized
    assert "event: final" in normalized
    assert "event: done" in normalized

    preview_blocks = [block for block in normalized.split("\n\n") if "event: preview" in block]
    assert preview_blocks
    preview_data = "\n".join(
        line.removeprefix("data: ")
        for line in preview_blocks[-1].splitlines()
        if line.startswith("data: ")
    )
    preview = json.loads(preview_data)
    assert preview["correctness"] == "mostly correct"
    assert preview["mastery_score"] == 74

    final_blocks = [block for block in normalized.split("\n\n") if "event: final" in block]
    assert final_blocks
    final_data = "\n".join(
        line.removeprefix("data: ")
        for line in final_blocks[-1].splitlines()
        if line.startswith("data: ")
    )
    payload = json.loads(final_data)

    assert payload["learning_mode"] == "socratic"
    assert payload["question_kind"] == "probe"
    assert payload["structured_feedback"]["mastery_score"] == 74
    assert payload["follow_up"]["needed"] is True
    assert payload["trace_id"]


@pytest.mark.asyncio
async def test_probe_response_never_triggers_advancement(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Probe response")

    async def fake_feedback(*args, **kwargs):
        return {
            "correctness": "correct",
            "misconceptions": [],
            "suggestions": ["name the causal link explicitly"],
            "next_question": "What evidence would confirm that link?",
            "mastery_score": 92,
            "dimension_scores": {"accuracy": 92, "completeness": 90, "transfer": 88, "rigor": 89},
            "confidence": 0.93,
            "pass_stage": True,
            "decision_reason": "Understanding looks strong but this was only a probe.",
        }

    monkeypatch.setattr(model_os_service, "generate_feedback_structured", fake_feedback)

    response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={"problem_id": problem["id"], "user_response": "Here is my first answer."},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["question_kind"] == "probe"
    assert body["decision"]["progression_ran"] is False
    assert body["decision"]["advance"] is False
    assert body["auto_advanced"] is False
    assert body["follow_up"]["needed"] is True
    assert body["follow_up"]["question_kind"] == "checkpoint"

    path_response = await client.get(
        f"/api/problems/{problem['id']}/learning-path",
        headers=headers,
    )
    assert path_response.status_code == 200
    assert path_response.json()["current_step"] == 0


@pytest.mark.asyncio
async def test_checkpoint_response_can_advance_after_probe(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Checkpoint response")

    async def fake_feedback(*args, **kwargs):
        return {
            "correctness": "correct",
            "misconceptions": [],
            "suggestions": ["keep the explanation compact"],
            "next_question": "What tradeoff matters most next?",
            "mastery_score": 90,
            "dimension_scores": {"accuracy": 90, "completeness": 88, "transfer": 87, "rigor": 86},
            "confidence": 0.9,
            "pass_stage": True,
            "decision_reason": "Stable understanding demonstrated.",
        }

    monkeypatch.setattr(model_os_service, "generate_feedback_structured", fake_feedback)

    first_response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={"problem_id": problem["id"], "user_response": "First answer."},
        headers=headers,
    )
    assert first_response.status_code == 200
    assert first_response.json()["question_kind"] == "probe"
    assert first_response.json()["auto_advanced"] is False

    second_response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={"problem_id": problem["id"], "user_response": "Second answer."},
        headers=headers,
    )
    assert second_response.status_code == 200
    second_body = second_response.json()
    assert second_body["question_kind"] == "checkpoint"
    assert second_body["decision"]["progression_ran"] is True
    assert second_body["decision"]["advance"] is True
    assert second_body["auto_advanced"] is True
    assert second_body["new_current_step"] == 1
    assert second_body["follow_up"]["needed"] is False

    responses = await client.get(
        f"/api/problems/{problem['id']}/responses",
        headers=headers,
    )
    assert responses.status_code == 200
    history = responses.json()
    assert history[0]["question_kind"] == "probe"
    assert history[1]["question_kind"] == "checkpoint"
    assert history[1]["decision"]["progression_ran"] is True

    path_response = await client.get(
        f"/api/problems/{problem['id']}/learning-path",
        headers=headers,
    )
    assert path_response.status_code == 200
    assert path_response.json()["current_step"] == 1


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
async def test_problem_ask_filters_low_signal_concept_candidates(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="PID", description="理解 PID 的比例、积分和微分")

    async def fake_answer(*args, **kwargs):
        return (
            "1. 简洁定义\n"
            "- 比例（P）：根据当前误差大小成比例地调整控制输出，响应快但可能存在稳态误差。\n"
            "- 积分（I）：累积过去所有误差，用于消除稳态误差，但可能降低系统响应速度。\n"
            "- 微分（D）：根据误差变化率预测未来趋势，抑制超调和振荡，但对噪声敏感。"
        )

    async def fake_extract(*args, **kwargs):
        return [
            "中的比例",
            "微分和积分是什么",
            "简洁定义",
            "比例",
            "根据当前误差大小成比例地",
        ]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "PID中的比例、微分和积分是什么",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    turn_candidates = {item["name"] for item in body["derived_candidates"]}

    assert "比例" in turn_candidates
    assert "中的比例" not in turn_candidates
    assert "微分和积分是什么" not in turn_candidates
    assert "简洁定义" not in turn_candidates
    assert "根据当前误差大小成比例地" not in turn_candidates

    candidates_response = await client.get(
        f"/api/problems/{problem['id']}/concept-candidates",
        headers=headers,
    )
    assert candidates_response.status_code == 200
    stored_turn_candidates = [
        item
        for item in candidates_response.json()
        if item["source_turn_id"] == body["turn_id"]
    ]
    stored_turn_candidate_names = {item["concept_text"] for item in stored_turn_candidates}
    assert "比例" in stored_turn_candidate_names
    assert "中的比例" not in stored_turn_candidate_names
    assert "微分和积分是什么" not in stored_turn_candidate_names
    assert "简洁定义" not in stored_turn_candidate_names
    assert "根据当前误差大小成比例地" not in stored_turn_candidate_names
    ratio_candidate = next(item for item in stored_turn_candidates if item["concept_text"] == "比例")
    assert "积分（I）" in ratio_candidate["evidence_snippet"]
    assert "对噪声敏感" in ratio_candidate["evidence_snippet"]


@pytest.mark.asyncio
async def test_problem_ask_strips_markdown_fragments_from_extracted_concepts(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(
        client,
        headers,
        title="精确率与召回率",
        description="理解精确率、召回率和阈值变化的关系。",
    )

    async def fake_answer(*args, **kwargs):
        return (
            "1. **精确率**：在所有被预测为正类的样本中，实际为正类的比例。\n"
            "2. **召回率**：在所有实际为正类的样本中，被预测为正类的比例。\n"
            "3. 在代码变更的缺陷检测中，降低阈值通常会提高召回率。"
        )

    async def fake_extract(*args, **kwargs):
        return [
            "1.**精确率",
            "召回率的定义**",
            "在代码变更的缺陷检测中",
        ]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "精确率和召回率有什么区别？",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()

    turn_candidates = {item["name"] for item in body["derived_candidates"]}
    assert "精确率" in turn_candidates
    assert "召回率" in turn_candidates
    assert "1.**精确率" not in turn_candidates
    assert "召回率的定义**" not in turn_candidates
    assert "在代码变更的缺陷检测中" not in turn_candidates

    candidates_response = await client.get(
        f"/api/problems/{problem['id']}/concept-candidates",
        headers=headers,
    )
    assert candidates_response.status_code == 200
    stored_turn_candidates = [
        item
        for item in candidates_response.json()
        if item["source_turn_id"] == body["turn_id"]
    ]
    stored_turn_candidate_names = {item["concept_text"] for item in stored_turn_candidates}
    assert "精确率" in stored_turn_candidate_names
    assert "召回率" in stored_turn_candidate_names
    assert "1.**精确率" not in stored_turn_candidate_names
    assert "召回率的定义**" not in stored_turn_candidate_names
    assert "在代码变更的缺陷检测中" not in stored_turn_candidate_names


@pytest.mark.asyncio
async def test_problem_ask_splits_enumerated_concepts_and_drops_instruction_tails(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(
        client,
        headers,
        title="Metric tradeoffs",
        description="Understand precision, recall, false positives, and false negatives.",
    )

    async def fake_answer(*args, **kwargs):
        return (
            "Precision measures the accuracy of predicted positives, recall measures the coverage of actual positives, "
            "false positives are incorrect positive predictions, and false negatives are missed positives."
        )

    async def fake_extract(*args, **kwargs):
        return [
            "false negatives in one concise explanation",
            "precision, recall, false positives",
        ]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "Please compare precision, recall, false positives, and false negatives in one concise explanation.",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()

    turn_candidates = {item["name"] for item in body["derived_candidates"]}
    assert "false negatives" in turn_candidates
    assert "precision" in turn_candidates
    assert "recall" in turn_candidates or "false positives" in turn_candidates
    assert "false negatives in one concise explanation" not in turn_candidates
    assert "precision, recall, false positives" not in turn_candidates

    candidates_response = await client.get(
        f"/api/problems/{problem['id']}/concept-candidates",
        headers=headers,
    )
    assert candidates_response.status_code == 200
    stored_turn_candidates = [
        item
        for item in candidates_response.json()
        if item["source_turn_id"] == body["turn_id"]
    ]
    stored_turn_candidate_names = {item["concept_text"] for item in stored_turn_candidates}
    assert "false negatives" in stored_turn_candidate_names
    assert "precision" in stored_turn_candidate_names
    assert "false negatives in one concise explanation" not in stored_turn_candidate_names
    assert "precision, recall, false positives" not in stored_turn_candidate_names


@pytest.mark.asyncio
async def test_problem_ask_caps_exploration_concept_candidates_to_three(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="PID tuning", description="Compare control terms")

    async def fake_answer(*args, **kwargs):
        return (
            "Proportional control reacts to the current error, integral control accumulates past error, "
            "derivative control damps fast changes, feedforward anticipates disturbances, and anti-windup "
            "keeps the integral term from saturating."
        )

    async def fake_extract(*args, **kwargs):
        return [
            "Proportional control",
            "Integral control",
            "Derivative control",
            "Feedforward control",
            "Anti-windup",
        ]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "How do proportional, integral, derivative, feedforward, and anti-windup compare?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert len(body["derived_candidates"]) == 3

    candidates_response = await client.get(
        f"/api/problems/{problem['id']}/concept-candidates",
        headers=headers,
    )
    assert candidates_response.status_code == 200
    stored_turn_candidates = [
        item
        for item in candidates_response.json()
        if item["source_turn_id"] == body["turn_id"]
    ]
    assert len(stored_turn_candidates) == 3


@pytest.mark.asyncio
async def test_problem_ask_returns_structured_exploration_artifacts(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Exploration artifacts")

    async def fake_answer(*args, **kwargs):
        return (
            "Model Predictive Control depends on a state-space model and uses "
            "receding horizon optimization to handle constraints."
        )

    async def fake_extract(*args, **kwargs):
        return [
            "Model Predictive Control",
            "State-space model",
            "Receding horizon optimization",
        ]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "What should I learn before Model Predictive Control?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["learning_mode"] == "exploration"
    assert body["answer_type"] == "prerequisite_explanation"
    assert "Model Predictive Control" in body["answered_concepts"]
    assert "State-space model" in body["related_concepts"]
    assert len(body["next_learning_actions"]) >= 2
    assert body["path_suggestions"]
    assert body["path_suggestions"][0]["type"] == "prerequisite"
    assert body["return_to_main_path_hint"] is False
    assert body["derived_candidates"]
    assert any(item["name"] == "Model Predictive Control" for item in body["derived_candidates"])
    assert body["mode_metadata"]["answer_type"] == "prerequisite_explanation"
    assert body["mode_metadata"]["path_suggestions"][0]["type"] == "prerequisite"

    turns_response = await client.get(
        f"/api/problems/{problem['id']}/turns",
        params={"learning_mode": "exploration"},
        headers=headers,
    )
    assert turns_response.status_code == 200
    turns = turns_response.json()
    assert turns
    latest_turn = turns[0]
    assert latest_turn["mode_metadata"]["answer_type"] == "prerequisite_explanation"
    assert latest_turn["mode_metadata"]["answered_concepts"][0] == "Model Predictive Control"
    assert latest_turn["mode_metadata"]["return_to_main_path_hint"] is False


@pytest.mark.asyncio
async def test_problem_ask_prioritizes_explicit_question_concepts_over_generic_step_concept(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    create_response = await client.post(
        "/api/problems/",
        json={
            "title": "Real Metrics Test",
            "description": "Understand precision, recall, and threshold tradeoffs.",
            "associated_concepts": ["precision", "recall"],
            "learning_mode": "exploration",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    problem = create_response.json()

    async def fake_answer(*args, **kwargs):
        return (
            "Precision measures how many predicted positives are correct, while recall measures "
            "how many actual positives are recovered."
        )

    async def fake_extract(*args, **kwargs):
        return ["Clarify goal and constraints"]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "What is the difference between precision and recall?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["answer_type"] == "comparison"
    assert body["answered_concepts"][:2] == ["precision", "recall"]
    assert any("precision" in item.lower() and "recall" in item.lower() for item in body["next_learning_actions"])
    assert body["path_suggestions"]
    assert "precision" in body["path_suggestions"][0]["title"].lower()
    assert "recall" in body["path_suggestions"][0]["title"].lower()
    assert "Clarify goal and constraints" not in " ".join(body["next_learning_actions"])

    candidates_response = await client.get(
        f"/api/problems/{problem['id']}/concept-candidates",
        headers=headers,
    )
    assert candidates_response.status_code == 200
    turn_candidates = [
        item
        for item in candidates_response.json()
        if item["source_turn_id"] == body["turn_id"]
    ]
    assert not any(item["concept_text"] == "Clarify goal and constraints" for item in turn_candidates)


@pytest.mark.asyncio
async def test_problem_ask_prefers_atomic_comparison_targets_over_comparison_step_label(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    async def fake_learning_path(*args, **kwargs):
        return [
            {
                "step": 1,
                "concept": "Compare precision and recall",
                "description": "Explain how precision differs from recall in one threshold-setting scenario.",
                "resources": ["precision", "recall"],
            }
        ]

    async def fake_answer(*args, **kwargs):
        return (
            "When the threshold rises, precision often improves because fewer cases are predicted positive, "
            "while recall often drops because more true positives are missed."
        )

    async def fake_extract(*args, **kwargs):
        return ["Compare precision and recall"]

    monkeypatch.setattr(model_os_service, "generate_learning_path", fake_learning_path)
    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    create_response = await client.post(
        "/api/problems/",
        json={
            "title": "Real Metrics Test",
            "description": "Understand precision, recall, and threshold tradeoffs.",
            "associated_concepts": ["precision", "recall"],
            "learning_mode": "exploration",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    problem = create_response.json()

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "How should I compare precision and recall when the threshold moves?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()

    assert body["answer_type"] == "comparison"
    assert body["answered_concepts"][:2] == ["precision", "recall"]
    assert all("compare precision and recall" not in item.lower() for item in body["answered_concepts"])
    assert any("precision" in item.lower() and "recall" in item.lower() for item in body["next_learning_actions"])
    assert all("compare precision and recall' and 'precision" not in item.lower() for item in body["next_learning_actions"])


@pytest.mark.asyncio
async def test_problem_ask_tolerates_duplicate_concept_alias_rows(client, db_session, monkeypatch):
    from app.models.entities.user import Concept, ConceptAlias
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_response = await client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    user_id = me_response.json()["id"]

    concept = Concept(
        user_id=user_id,
        canonical_name="precision",
        normalized_name="precision",
        language="auto",
        status="active",
    )
    db_session.add(concept)
    await db_session.flush()
    db_session.add_all(
        [
            ConceptAlias(concept_id=concept.id, alias="precision", normalized_alias="precision"),
            ConceptAlias(concept_id=concept.id, alias="Precision", normalized_alias="precision"),
        ]
    )
    await db_session.commit()

    create_response = await client.post(
        "/api/problems/",
        json={
            "title": "Real Metrics Test",
            "description": "Understand precision, recall, and threshold tradeoffs.",
            "associated_concepts": ["precision", "recall"],
            "learning_mode": "exploration",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    problem = create_response.json()

    async def fake_answer(*args, **kwargs):
        return "Precision and recall move in opposite directions as the threshold rises."

    async def fake_extract(*args, **kwargs):
        return ["precision", "recall"]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "How should I compare precision and recall when the threshold moves?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["answered_concepts"][:2] == ["precision", "recall"]


@pytest.mark.asyncio
async def test_problem_response_generates_path_candidates_in_socratic_mode(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Socratic path candidates")

    async def fake_feedback(*args, **kwargs):
        return {
            "correctness": "partially correct",
            "misconceptions": ["Missing prerequisite foundation"],
            "suggestions": ["Compare the current concept with its prerequisite"],
            "next_question": "What is the difference between the prerequisite and this concept?",
            "mastery_score": 52,
            "dimension_scores": {"accuracy": 52, "completeness": 50, "transfer": 48, "rigor": 49},
            "confidence": 0.61,
            "pass_stage": False,
            "decision_reason": "The learner still lacks foundation.",
        }

    monkeypatch.setattr(model_os_service, "generate_feedback_structured", fake_feedback)

    response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={"problem_id": problem["id"], "user_response": "I am still mixing up the prerequisite."},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["learning_mode"] == "socratic"
    assert body["derived_path_candidates"]
    assert body["derived_path_candidates"][0]["type"] == "prerequisite"
    assert body["derived_path_candidates"][0]["source_turn_id"] == body["turn_id"]

    candidates_response = await client.get(
        f"/api/problems/{problem['id']}/path-candidates",
        headers=headers,
    )
    assert candidates_response.status_code == 200
    candidates = candidates_response.json()
    assert any(
        item["learning_mode"] == "socratic"
        and item["source_turn_id"] == body["turn_id"]
        for item in candidates
    )


@pytest.mark.asyncio
async def test_problem_path_candidates_from_exploration_can_be_decided(client, db_session, monkeypatch):
    from app.models.entities.user import ProblemPathCandidate
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Exploration path candidates")

    async def fake_answer(*args, **kwargs):
        return "Model Predictive Control depends on state-space modeling first."

    async def fake_extract(*args, **kwargs):
        return [
            "Model Predictive Control",
            "State-space model",
            "Constraint handling",
        ]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "What should I learn before Model Predictive Control?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["derived_path_candidates"]
    candidate = body["derived_path_candidates"][0]
    assert candidate["type"] == "prerequisite"
    assert candidate["recommended_insertion"] == "insert_before_current_main"
    assert candidate["source_turn_id"] == body["turn_id"]

    decision_response = await client.post(
        f"/api/problems/{problem['id']}/path-candidates/{candidate['id']}/decide",
        json={"action": "insert_before_current_main"},
        headers=headers,
    )
    assert decision_response.status_code == 200
    decision_body = decision_response.json()
    assert decision_body["candidate"]["status"] == "planned"
    assert decision_body["candidate"]["selected_insertion"] == "insert_before_current_main"

    candidates_response = await client.get(
        f"/api/problems/{problem['id']}/path-candidates",
        headers=headers,
    )
    assert candidates_response.status_code == 200
    candidates = candidates_response.json()
    assert any(
        item["id"] == candidate["id"]
        and item["learning_mode"] == "exploration"
        and item["status"] == "planned"
        for item in candidates
    )

    result = await db_session.execute(
        select(ProblemPathCandidate).where(ProblemPathCandidate.id == candidate["id"])
    )
    stored = result.scalar_one()
    assert stored.status == "planned"
    assert stored.selected_insertion == "insert_before_current_main"


@pytest.mark.asyncio
async def test_redeciding_insert_before_current_main_reactivates_main_path(client, db_session, monkeypatch):
    from app.models.entities.user import LearningPath
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Main path reactivation")

    async def fake_answer(*args, **kwargs):
        return "Model Predictive Control depends on state-space modeling first."

    async def fake_extract(*args, **kwargs):
        return [
            "Model Predictive Control",
            "State-space model",
            "Constraint handling",
        ]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "What should I learn before Model Predictive Control?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    candidate = ask_response.json()["derived_path_candidates"][0]

    first_decision = await client.post(
        f"/api/problems/{problem['id']}/path-candidates/{candidate['id']}/decide",
        json={"action": "insert_before_current_main"},
        headers=headers,
    )
    assert first_decision.status_code == 200

    active_main_response = await client.get(
        f"/api/problems/{problem['id']}/learning-path",
        headers=headers,
    )
    assert active_main_response.status_code == 200
    active_main = active_main_response.json()
    assert active_main["kind"] == "main"
    main_path_id = active_main["id"]
    main_step_count = len(active_main["path_data"])
    main_current_step = active_main["current_step"]

    branch_path = LearningPath(
        problem_id=problem["id"],
        title="Temporary branch detour",
        kind="branch",
        parent_path_id=main_path_id,
        source_turn_id=candidate["source_turn_id"],
        return_step_id=0,
        branch_reason="Temporary detour for reactivation coverage.",
        is_active=False,
        path_data=[
            {
                "step": 1,
                "concept": "Temporary branch detour",
                "description": "Use a temporary branch to verify reactivation.",
                "resources": [],
            }
        ],
        current_step=0,
    )
    db_session.add(branch_path)
    await db_session.commit()

    activate_branch = await client.post(
        f"/api/problems/{problem['id']}/learning-paths/{branch_path.id}/activate",
        headers=headers,
    )
    assert activate_branch.status_code == 200
    assert activate_branch.json()["id"] == str(branch_path.id)

    repeat_decision = await client.post(
        f"/api/problems/{problem['id']}/path-candidates/{candidate['id']}/decide",
        json={"action": "insert_before_current_main"},
        headers=headers,
    )
    assert repeat_decision.status_code == 200
    assert repeat_decision.json()["candidate"]["selected_insertion"] == "insert_before_current_main"

    restored_path = await client.get(
        f"/api/problems/{problem['id']}/learning-path",
        headers=headers,
    )
    assert restored_path.status_code == 200
    restored_body = restored_path.json()
    assert restored_body["id"] == main_path_id
    assert restored_body["kind"] == "main"
    assert len(restored_body["path_data"]) == main_step_count
    assert restored_body["current_step"] == main_current_step


@pytest.mark.asyncio
async def test_save_as_branch_creates_navigable_learning_path_and_return_flow(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Branch navigation")

    async def fake_answer(*args, **kwargs):
        return "Model Predictive Control depends on state-space modeling first."

    async def fake_extract(*args, **kwargs):
        return [
            "Model Predictive Control",
            "State-space model",
            "Constraint handling",
        ]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "What should I learn before Model Predictive Control?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    candidate = ask_response.json()["derived_path_candidates"][0]

    decide_response = await client.post(
        f"/api/problems/{problem['id']}/path-candidates/{candidate['id']}/decide",
        json={"action": "save_as_side_branch"},
        headers=headers,
    )
    assert decide_response.status_code == 200
    assert decide_response.json()["candidate"]["status"] == "planned"
    assert decide_response.json()["candidate"]["selected_insertion"] == "save_as_side_branch"

    active_path = await client.get(
        f"/api/problems/{problem['id']}/learning-path",
        headers=headers,
    )
    assert active_path.status_code == 200
    active_body = active_path.json()
    assert active_body["kind"] == "prerequisite"
    assert active_body["parent_path_id"] is not None
    assert active_body["return_step_id"] == 0
    assert active_body["is_active"] is True

    path_list = await client.get(
        f"/api/problems/{problem['id']}/learning-paths",
        headers=headers,
    )
    assert path_list.status_code == 200
    paths = path_list.json()
    assert any(item["kind"] == "main" for item in paths)
    assert any(item["kind"] == "prerequisite" for item in paths)
    main_path = next(item for item in paths if item["kind"] == "main")

    return_response = await client.post(
        f"/api/problems/{problem['id']}/learning-path/return",
        headers=headers,
    )
    assert return_response.status_code == 200
    assert return_response.json()["kind"] == "main"
    assert return_response.json()["id"] == main_path["id"]

    activate_branch = await client.post(
        f"/api/problems/{problem['id']}/learning-paths/{active_body['id']}/activate",
        headers=headers,
    )
    assert activate_branch.status_code == 200
    assert activate_branch.json()["id"] == active_body["id"]
    assert activate_branch.json()["kind"] == "prerequisite"


@pytest.mark.asyncio
async def test_branch_repeated_concept_keeps_branch_specific_candidate_for_reinforcement(
    client, db_session, monkeypatch
):
    from app.models.entities.user import ProblemConceptCandidate, ProblemTurn
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Branch reinforcement precision")

    async def fake_answer(*args, **kwargs):
        return "Decision threshold changes the balance between precision and recall."

    async def fake_extract(*args, **kwargs):
        return [
            "Decision threshold",
            "False negatives",
            "Precision-recall tradeoff",
        ]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    first_ask = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "What is the difference between decision threshold and precision-recall tradeoff?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert first_ask.status_code == 200
    first_body = first_ask.json()
    branch_candidate = first_body["derived_path_candidates"][0]

    decide_response = await client.post(
        f"/api/problems/{problem['id']}/path-candidates/{branch_candidate['id']}/decide",
        json={"action": "save_as_side_branch"},
        headers=headers,
    )
    assert decide_response.status_code == 200
    active_path_response = await client.get(
        f"/api/problems/{problem['id']}/learning-path",
        headers=headers,
    )
    assert active_path_response.status_code == 200
    branch_path = active_path_response.json()
    assert branch_path["id"]

    second_ask = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "How should I compare precision and recall when the threshold moves?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert second_ask.status_code == 200
    second_body = second_ask.json()

    candidates_response = await client.get(
        f"/api/problems/{problem['id']}/concept-candidates",
        headers=headers,
    )
    assert candidates_response.status_code == 200
    threshold_candidates = [
        item for item in candidates_response.json()
        if item["concept_text"] == "Decision threshold"
    ]
    assert len(threshold_candidates) >= 2

    latest_branch_candidate = next(
        item for item in threshold_candidates if item["source_turn_id"] == second_body["turn_id"]
    )
    first_main_candidate = next(
        item for item in threshold_candidates if item["source_turn_id"] == first_body["turn_id"]
    )
    assert latest_branch_candidate["source_turn_id"] != first_main_candidate["source_turn_id"]

    turn_rows = await db_session.execute(
        select(ProblemTurn).where(
            ProblemTurn.id.in_([first_body["turn_id"], second_body["turn_id"]])
        )
    )
    turns_by_id = {str(turn.id): turn for turn in turn_rows.scalars().all()}
    assert turns_by_id[first_body["turn_id"]].path_id != turns_by_id[second_body["turn_id"]].path_id
    assert turns_by_id[second_body["turn_id"]].path_id == branch_path["id"]

    accept_response = await client.post(
        f"/api/problems/{problem['id']}/concept-candidates/{latest_branch_candidate['id']}/accept",
        headers=headers,
    )
    assert accept_response.status_code == 200

    schedule_response = await client.post(
        f"/api/problems/{problem['id']}/concept-candidates/{latest_branch_candidate['id']}/schedule-review",
        headers=headers,
    )
    assert schedule_response.status_code == 200
    model_card_id = schedule_response.json()["model_card"]["id"]

    schedules_response = await client.get("/api/srs/schedules", headers=headers)
    assert schedules_response.status_code == 200
    schedule = next(
        item for item in schedules_response.json()
        if item["model_card_id"] == model_card_id
    )
    assert schedule["origin"]["source_turn_id"] == second_body["turn_id"]
    assert schedule["origin"]["source_path_id"] == branch_path["id"]

    review_response = await client.post(
        f"/api/srs/review/{schedule['schedule_id']}?quality=0",
        headers=headers,
    )
    assert review_response.status_code == 200
    review_body = review_response.json()
    assert review_body["reinforcement_target"]["resume_path_id"] == branch_path["id"]

    refreshed_candidates = await db_session.execute(
        select(ProblemConceptCandidate).where(
            ProblemConceptCandidate.id.in_([
                latest_branch_candidate["id"],
                first_main_candidate["id"],
            ])
        )
    )
    stored_candidates = {str(candidate.id): candidate for candidate in refreshed_candidates.scalars().all()}
    assert stored_candidates[latest_branch_candidate["id"]].linked_model_card_id is not None
    assert stored_candidates[first_main_candidate["id"]].source_turn_id != stored_candidates[latest_branch_candidate["id"]].source_turn_id


@pytest.mark.asyncio
async def test_insert_before_current_main_updates_main_path(client, monkeypatch):
    from app.services.model_os_service import model_os_service

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    problem = await create_problem(client, headers, title="Main path insertion")

    before_path = await client.get(
        f"/api/problems/{problem['id']}/learning-path",
        headers=headers,
    )
    assert before_path.status_code == 200
    before_body = before_path.json()
    before_count = len(before_body["path_data"])

    async def fake_answer(*args, **kwargs):
        return "Model Predictive Control depends on state-space modeling first."

    async def fake_extract(*args, **kwargs):
        return [
            "Model Predictive Control",
            "State-space model",
            "Constraint handling",
        ]

    monkeypatch.setattr(model_os_service, "generate_with_context", fake_answer)
    monkeypatch.setattr(model_os_service, "extract_related_concepts_resilient", fake_extract)

    ask_response = await client.post(
        f"/api/problems/{problem['id']}/ask",
        json={
            "question": "What should I learn before Model Predictive Control?",
            "learning_mode": "exploration",
            "answer_mode": "direct",
        },
        headers=headers,
    )
    assert ask_response.status_code == 200
    candidate = ask_response.json()["derived_path_candidates"][0]

    decide_response = await client.post(
        f"/api/problems/{problem['id']}/path-candidates/{candidate['id']}/decide",
        json={"action": "insert_before_current_main"},
        headers=headers,
    )
    assert decide_response.status_code == 200
    assert decide_response.json()["candidate"]["selected_insertion"] == "insert_before_current_main"

    after_path = await client.get(
        f"/api/problems/{problem['id']}/learning-path",
        headers=headers,
    )
    assert after_path.status_code == 200
    after_body = after_path.json()
    assert after_body["kind"] == "main"
    assert len(after_body["path_data"]) >= before_count + 2
    assert after_body["current_step"] == 0
    assert "State-space model" in after_body["path_data"][0]["concept"] or candidate["title"] in after_body["path_data"][0]["concept"]


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
