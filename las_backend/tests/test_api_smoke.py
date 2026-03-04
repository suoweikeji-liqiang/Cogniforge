import pytest


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
    body = login_response.json()
    return body


async def create_model_card(client, headers, title="Vector Search", user_notes="semantic retrieval"):
    response = await client.post(
        "/api/model-cards/",
        json={
            "title": title,
            "user_notes": user_notes,
            "examples": ["embedding", "ranking"],
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def promote_user_to_admin(db_session, username="tester"):
    from sqlalchemy import select

    from app.models.entities.user import User

    result = await db_session.execute(select(User).where(User.username == username))
    user = result.scalar_one()
    user.role = "admin"
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_auth_refresh_and_logout_flow(client, db_session):
    from sqlalchemy import select

    from app.models.entities.user import RevokedToken

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    me_response = await client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "tester"

    refresh_response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    refreshed_body = refresh_response.json()
    refreshed_token = refreshed_body["access_token"]
    assert refreshed_token
    assert refreshed_body["refresh_token"] != tokens["refresh_token"]

    replay_refresh_response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert replay_refresh_response.status_code == 401

    revoked_after_refresh = await db_session.execute(
        select(RevokedToken).where(RevokedToken.token == tokens["refresh_token"])
    )
    revoked_refresh = revoked_after_refresh.scalar_one()
    assert revoked_refresh.token_type == "refresh"
    assert revoked_refresh.expires_at is not None

    refreshed_headers = {"Authorization": f"Bearer {refreshed_token}"}
    logout_response = await client.post(
        "/api/auth/logout",
        json={
            "access_token": refreshed_token,
            "refresh_token": refreshed_body["refresh_token"],
        },
    )
    assert logout_response.status_code == 200

    revoked_tokens = await db_session.execute(
        select(RevokedToken).where(
            RevokedToken.token.in_(
                [
                    tokens["refresh_token"],
                    refreshed_token,
                    refreshed_body["refresh_token"],
                ]
            )
        )
    )
    revoked_payloads = {item.token: item.token_type for item in revoked_tokens.scalars().all()}
    assert revoked_payloads[tokens["refresh_token"]] == "refresh"
    assert revoked_payloads[refreshed_token] == "access"
    assert revoked_payloads[refreshed_body["refresh_token"]] == "refresh"

    me_after_logout = await client.get("/api/auth/me", headers=refreshed_headers)
    assert me_after_logout.status_code == 401


@pytest.mark.asyncio
async def test_model_card_search_and_similar(client):
    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    alpha = await create_model_card(client, headers, "Vector Search", "semantic retrieval")
    beta_response = await client.post(
        "/api/model-cards/",
        json={"title": "Vector Similarity", "user_notes": "cosine distance", "examples": ["embedding", "neighbors"]},
        headers=headers,
    )
    gamma_response = await client.post(
        "/api/model-cards/",
        json={"title": "SQL Basics", "user_notes": "joins and filters", "examples": ["select"]},
        headers=headers,
    )
    assert beta_response.status_code == 201
    assert gamma_response.status_code == 201

    search_response = await client.get("/api/model-cards/", params={"q": "semantic embedding"}, headers=headers)
    assert search_response.status_code == 200
    titles = [item["title"] for item in search_response.json()]
    assert "Vector Search" in titles
    assert "Vector Similarity" in titles

    similar_response = await client.get(
        f"/api/model-cards/{alpha['id']}/similar",
        headers=headers,
    )
    assert similar_response.status_code == 200
    similar_titles = [item["title"] for item in similar_response.json()]
    assert "Vector Similarity" in similar_titles


@pytest.mark.asyncio
async def test_problem_and_resource_search(client):
    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    problem_response = await client.post(
        "/api/problems/",
        json={
            "title": "Need pgvector search",
            "description": "Find semantically related notes",
            "associated_concepts": ["pgvector", "retrieval"],
        },
        headers=headers,
    )
    assert problem_response.status_code == 201

    resource_response = await client.post(
        "/api/resources/",
        json={
            "url": "https://example.com/pgvector",
            "title": "pgvector guide",
            "link_type": "webpage",
        },
        headers=headers,
    )
    assert resource_response.status_code == 201

    problem_search = await client.get("/api/problems/", params={"q": "semantic retrieval"}, headers=headers)
    assert problem_search.status_code == 200
    assert any(item["title"] == "Need pgvector search" for item in problem_search.json())

    resource_search = await client.get("/api/resources/", params={"q": "pgvector guide"}, headers=headers)
    assert resource_search.status_code == 200
    assert any(item["title"] == "pgvector guide" for item in resource_search.json())


@pytest.mark.asyncio
async def test_retrieval_logs_and_summary(client):
    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await create_model_card(client, headers, "Retrieval Signals", "semantic cues and prior knowledge")
    problem_response = await client.post(
        "/api/problems/",
        json={
            "title": "Need stronger retrieval context",
            "description": "Connect current answer to prior model cards",
            "associated_concepts": ["retrieval", "memory"],
        },
        headers=headers,
    )
    assert problem_response.status_code == 201
    problem = problem_response.json()

    create_response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        json={"problem_id": problem["id"], "user_response": "I should connect this with old cards."},
        headers=headers,
    )
    assert create_response.status_code == 200

    conversation_response = await client.post(
        "/api/conversations/",
        json={"title": "Retrieval Chat"},
        headers=headers,
    )
    assert conversation_response.status_code == 201
    conversation = conversation_response.json()

    chat_response = await client.post(
        "/api/conversations/chat",
        json={
            "conversation_id": conversation["id"],
            "message": "Use my prior knowledge to answer this question.",
        },
        headers=headers,
    )
    assert chat_response.status_code == 200

    logs_response = await client.get("/api/retrieval/logs", headers=headers)
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) >= 2
    sources = {item["source"] for item in logs}
    assert "problem_response" in sources
    assert "conversation_chat" in sources
    assert any(log["result_count"] > 0 for log in logs)
    assert any(
        entry["entity_type"] == "model_card"
        for log in logs
        for entry in log["items"]
    )

    filtered_logs_response = await client.get(
        "/api/retrieval/logs",
        params={"source": "conversation_chat"},
        headers=headers,
    )
    assert filtered_logs_response.status_code == 200
    assert all(item["source"] == "conversation_chat" for item in filtered_logs_response.json())

    summary_response = await client.get("/api/retrieval/summary", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["total_events"] >= 2
    assert summary["total_hits"] >= 2
    assert summary["zero_hit_events"] == 0
    assert summary["poor_hit_events"] >= 1
    assert summary["zero_hit_rate"] == 0
    assert summary["health_status"] == "healthy"
    assert summary["source_breakdown"]["problem_response"] >= 1
    assert summary["source_breakdown"]["conversation_chat"] >= 1


@pytest.mark.asyncio
async def test_login_rate_limit(client, db_session):
    from sqlalchemy import select

    from app.models.entities.user import LoginThrottle

    await register_and_login(client)

    for _ in range(5):
        response = await client.post(
            "/api/auth/login",
            data={"username": "tester", "password": "wrong-password"},
        )
        assert response.status_code == 401

    blocked_response = await client.post(
        "/api/auth/login",
        data={"username": "tester", "password": "wrong-password"},
    )
    assert blocked_response.status_code == 429

    throttle_rows = await db_session.execute(select(LoginThrottle))
    throttles = throttle_rows.scalars().all()
    assert len(throttles) == 3
    assert all(item.failed_count == 5 for item in throttles)
    assert all(item.blocked_until is not None for item in throttles)


@pytest.mark.asyncio
async def test_reviews_generate_export_and_delete(client):
    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    problem_response = await client.post(
        "/api/problems/",
        json={
            "title": "Spaced repetition gap",
            "description": "Need to remember retrieval cues",
            "associated_concepts": ["memory", "srs"],
        },
        headers=headers,
    )
    assert problem_response.status_code == 201

    generated_response = await client.post(
        "/api/reviews/generate",
        json={"review_type": "weekly", "period": "2026-W10"},
        headers=headers,
    )
    assert generated_response.status_code == 200
    generated = generated_response.json()
    assert generated["review_type"] == "weekly"
    assert generated["period"] == "2026-W10"
    assert "summary" in generated["content"]
    assert "next_steps" in generated["content"]

    create_response = await client.post(
        "/api/reviews/",
        json={
            "review_type": generated["review_type"],
            "period": generated["period"],
            "content": generated["content"],
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    review = create_response.json()

    list_response = await client.get("/api/reviews/", headers=headers)
    assert list_response.status_code == 200
    assert any(item["id"] == review["id"] for item in list_response.json())

    export_response = await client.get(f"/api/reviews/{review['id']}/export", headers=headers)
    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("text/markdown")
    export_body = export_response.text
    assert "# Weekly Review" in export_body
    assert "2026-W10" in export_body

    update_response = await client.put(
        f"/api/reviews/{review['id']}",
        json={"content": {"summary": "Updated summary", "insights": "Updated insight", "next_steps": "Ship tests", "misconceptions": []}},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["content"]["summary"] == "Updated summary"

    delete_response = await client.delete(f"/api/reviews/{review['id']}", headers=headers)
    assert delete_response.status_code == 204

    missing_response = await client.get(f"/api/reviews/{review['id']}", headers=headers)
    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_srs_schedule_due_and_review_flow(client, db_session):
    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    card = await create_model_card(client, headers, "Retrieval Practice", "testing memory")

    schedule_response = await client.post(f"/api/srs/schedule/{card['id']}", headers=headers)
    assert schedule_response.status_code == 200
    schedule = schedule_response.json()
    assert schedule["id"]
    assert schedule["next_review_at"]

    duplicate_response = await client.post(f"/api/srs/schedule/{card['id']}", headers=headers)
    assert duplicate_response.status_code == 400

    schedules_response = await client.get("/api/srs/schedules", headers=headers)
    assert schedules_response.status_code == 200
    schedules = schedules_response.json()
    assert len(schedules) == 1
    assert schedules[0]["title"] == "Retrieval Practice"
    assert schedules[0]["interval_days"] == 1

    from datetime import datetime, timedelta

    from app.models.entities.user import ReviewSchedule

    schedule_id = schedule["id"]
    persisted_schedule = await db_session.get(ReviewSchedule, schedule_id)
    persisted_schedule.next_review_at = datetime.utcnow() - timedelta(minutes=5)
    await db_session.commit()

    due_response = await client.get("/api/srs/due", headers=headers)
    assert due_response.status_code == 200
    due_cards = due_response.json()
    assert len(due_cards) == 1
    assert due_cards[0]["schedule_id"] == schedule_id
    assert due_cards[0]["title"] == "Retrieval Practice"

    review_response = await client.post(
        f"/api/srs/review/{schedule_id}",
        params={"quality": 5},
        headers=headers,
    )
    assert review_response.status_code == 200
    reviewed = review_response.json()
    assert reviewed["repetitions"] == 1
    assert reviewed["interval_days"] == 1
    assert reviewed["ease_factor"] >= 2500


@pytest.mark.asyncio
async def test_practice_tasks_and_submissions_flow(client):
    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    card = await create_model_card(client, headers, "Practice Card", "practice retrieval")

    create_task_response = await client.post(
        "/api/practice/tasks",
        json={
            "title": "Explain retrieval practice",
            "description": "Write a short explanation",
            "task_type": "short_answer",
            "model_card_id": card["id"],
        },
        headers=headers,
    )
    assert create_task_response.status_code == 201
    task = create_task_response.json()
    assert task["title"] == "Explain retrieval practice"

    list_tasks_response = await client.get("/api/practice/tasks", headers=headers)
    assert list_tasks_response.status_code == 200
    assert any(item["id"] == task["id"] for item in list_tasks_response.json())

    create_submission_response = await client.post(
        "/api/practice/submissions",
        json={
            "practice_task_id": task["id"],
            "solution": "Retrieval practice strengthens recall by forcing memory access.",
        },
        headers=headers,
    )
    assert create_submission_response.status_code == 201
    submission = create_submission_response.json()
    assert submission["structured_feedback"]["correctness"] == "partially correct"
    assert submission["practice_task_id"] == task["id"]

    list_submissions_response = await client.get("/api/practice/submissions", headers=headers)
    assert list_submissions_response.status_code == 200
    assert any(item["id"] == submission["id"] for item in list_submissions_response.json())

    get_submission_response = await client.get(
        f"/api/practice/submissions/{submission['id']}",
        headers=headers,
    )
    assert get_submission_response.status_code == 200
    assert get_submission_response.json()["id"] == submission["id"]

    delete_task_response = await client.delete(f"/api/practice/tasks/{task['id']}", headers=headers)
    assert delete_task_response.status_code == 204

    missing_task_response = await client.delete(f"/api/practice/tasks/{task['id']}", headers=headers)
    assert missing_task_response.status_code == 404


@pytest.mark.asyncio
async def test_challenges_generate_answer_and_filter(client):
    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await create_model_card(client, headers, "Challenge Card", "boundary testing")

    generate_response = await client.post("/api/challenges/generate", headers=headers)
    assert generate_response.status_code == 200
    challenge = generate_response.json()
    assert challenge["status"] == "pending"
    assert challenge["question"]

    pending_response = await client.get("/api/challenges/", params={"status": "pending"}, headers=headers)
    assert pending_response.status_code == 200
    assert any(item["id"] == challenge["id"] for item in pending_response.json())

    answer_response = await client.post(
        f"/api/challenges/{challenge['id']}/answer",
        params={"answer": "I would test the boundary conditions and edge cases."},
        headers=headers,
    )
    assert answer_response.status_code == 200
    answered = answer_response.json()
    assert answered["status"] == "answered"
    assert answered["structured_feedback"]["suggestions"] == ["test suggestion"]

    answered_response = await client.get("/api/challenges/", params={"status": "answered"}, headers=headers)
    assert answered_response.status_code == 200
    answered_items = answered_response.json()
    assert any(item["id"] == challenge["id"] and item["status"] == "answered" for item in answered_items)


@pytest.mark.asyncio
async def test_conversations_and_chat_flow(client, monkeypatch):
    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    async def fake_counter_examples(model_title, model_concepts, user_response):
        return [f"Counter example for {model_title}"]

    async def fake_migrations(model_title, model_concepts):
        return [{"domain": "biology", "application": "Apply the same reasoning", "key_adaptations": "Adjust terminology"}]

    from app.services.model_os_service import model_os_service

    monkeypatch.setattr(model_os_service, "generate_counter_examples", fake_counter_examples)
    monkeypatch.setattr(model_os_service, "suggest_migration", fake_migrations)

    create_response = await client.post(
        "/api/conversations/",
        json={"title": "Learning Chat"},
        headers=headers,
    )
    assert create_response.status_code == 201
    conversation = create_response.json()
    assert conversation["title"] == "Learning Chat"

    list_response = await client.get("/api/conversations/", headers=headers)
    assert list_response.status_code == 200
    assert any(item["id"] == conversation["id"] for item in list_response.json())

    update_response = await client.put(
        f"/api/conversations/{conversation['id']}",
        json={"title": "Updated Chat"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated Chat"

    chat_response = await client.post(
        "/api/conversations/chat",
        json={
            "conversation_id": conversation["id"],
            "message": "Help me reason about retrieval practice.",
            "generate_contradiction": True,
            "suggest_migration": True,
        },
        headers=headers,
    )
    assert chat_response.status_code == 200
    chat_body = chat_response.json()
    assert chat_body["conversation_id"] == conversation["id"]
    assert chat_body["message"] == "stubbed contextual response"
    assert chat_body["metadata"]["counter_examples"] == ["Counter example for Updated Chat"]
    assert chat_body["metadata"]["migrations"][0]["domain"] == "biology"

    get_response = await client.get(f"/api/conversations/{conversation['id']}", headers=headers)
    assert get_response.status_code == 200
    messages = get_response.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

    delete_response = await client.delete(f"/api/conversations/{conversation['id']}", headers=headers)
    assert delete_response.status_code == 204

    missing_response = await client.get(f"/api/conversations/{conversation['id']}", headers=headers)
    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_admin_users_and_llm_config_flow(client, db_session, monkeypatch):
    import openai

    tokens = await register_and_login(client)
    await promote_user_to_admin(db_session)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    second_user_response = await client.post(
        "/api/auth/register",
        json={
            "email": "other@example.com",
            "username": "other-user",
            "password": "secret123",
            "full_name": "Other User",
        },
    )
    assert second_user_response.status_code == 201
    second_user = second_user_response.json()

    list_users_response = await client.get("/api/admin/users", headers=headers)
    assert list_users_response.status_code == 200
    assert len(list_users_response.json()) == 2

    stats_response = await client.get("/api/admin/users/stats", headers=headers)
    assert stats_response.status_code == 200
    assert stats_response.json()["users"] == 2

    update_user_response = await client.put(
        f"/api/admin/users/{second_user['id']}",
        json={"full_name": "Updated User", "is_active": False},
        headers=headers,
    )
    assert update_user_response.status_code == 200
    assert update_user_response.json()["full_name"] == "Updated User"
    assert update_user_response.json()["is_active"] is False

    create_provider_response = await client.post(
        "/api/admin/llm-config/providers",
        json={
            "name": "Qwen Main",
            "provider_type": "qwen",
            "api_key": "super-secret-key",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "enabled": True,
            "priority": 1,
        },
        headers=headers,
    )
    assert create_provider_response.status_code == 200
    provider_id = create_provider_response.json()["id"]

    providers_response = await client.get("/api/admin/llm-config/providers", headers=headers)
    assert providers_response.status_code == 200
    provider = providers_response.json()[0]
    assert provider["id"] == provider_id
    assert provider["api_key"] == "Configured"

    create_model_response = await client.post(
        "/api/admin/llm-config/models",
        json={
            "provider_id": provider_id,
            "model_id": "qwen-plus",
            "model_name": "Qwen Plus",
            "enabled": True,
            "is_default": True,
        },
        headers=headers,
    )
    assert create_model_response.status_code == 200
    llm_model_id = create_model_response.json()["id"]

    update_model_response = await client.put(
        f"/api/admin/llm-config/models/{llm_model_id}",
        json={"model_name": "Qwen Plus Updated", "enabled": False},
        headers=headers,
    )
    assert update_model_response.status_code == 200

    providers_after_model_response = await client.get("/api/admin/llm-config/providers", headers=headers)
    assert providers_after_model_response.status_code == 200
    model = providers_after_model_response.json()[0]["models"][0]
    assert model["model_name"] == "Qwen Plus Updated"
    assert model["enabled"] is False

    class FakeOpenAI:
        def __init__(self, api_key, base_url=None):
            self.api_key = api_key
            self.base_url = base_url
            self.chat = self
            self.completions = self

        def create(self, model, messages, max_tokens):
            assert self.api_key == "super-secret-key"
            assert self.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
            assert model == "qwen-plus"
            return {"ok": True}

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    provider_test_response = await client.get(
        f"/api/admin/llm-config/providers/{provider_id}/test",
        headers=headers,
    )
    assert provider_test_response.status_code == 200
    assert provider_test_response.json()["status"] == "success"

    delete_model_response = await client.delete(
        f"/api/admin/llm-config/models/{llm_model_id}",
        headers=headers,
    )
    assert delete_model_response.status_code == 200

    delete_provider_response = await client.delete(
        f"/api/admin/llm-config/providers/{provider_id}",
        headers=headers,
    )
    assert delete_provider_response.status_code == 200

    self_delete_response = await client.delete(
        f"/api/admin/users/{(await promote_user_to_admin(db_session)).id}",
        headers=headers,
    )
    assert self_delete_response.status_code == 400

    delete_other_response = await client.delete(
        f"/api/admin/users/{second_user['id']}",
        headers=headers,
    )
    assert delete_other_response.status_code == 204


@pytest.mark.asyncio
async def test_password_reset_flow(client, db_session, monkeypatch):
    import smtplib

    from sqlalchemy import select

    from app.models.entities.email_config import EmailConfig
    from app.models.entities.user import PasswordResetToken

    await register_and_login(client)

    db_session.add(
        EmailConfig(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="mailer",
            smtp_password="password",
            from_email="noreply@example.com",
            from_name="Cogniforge",
            use_tls=True,
            is_active=True,
        )
    )
    await db_session.commit()

    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port):
            assert host == "smtp.example.com"
            assert port == 587

        def starttls(self):
            return None

        def login(self, user, password):
            assert user == "mailer"
            assert password == "password"

        def sendmail(self, from_email, to_email, content):
            sent_messages.append((from_email, to_email, content))

        def quit(self):
            return None

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    forgot_response = await client.post(
        "/api/auth/forgot-password",
        json={"email": "user@example.com"},
    )
    assert forgot_response.status_code == 200
    assert sent_messages

    token_result = await db_session.execute(select(PasswordResetToken))
    token_record = token_result.scalar_one()

    verify_response = await client.get(
        "/api/auth/verify-reset-token",
        params={"token": token_record.token},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["valid"] is True

    reset_response = await client.post(
        "/api/auth/reset-password",
        json={"token": token_record.token, "new_password": "new-secret123"},
    )
    assert reset_response.status_code == 200

    reused_token_response = await client.get(
        "/api/auth/verify-reset-token",
        params={"token": token_record.token},
    )
    assert reused_token_response.status_code == 400

    relogin_response = await client.post(
        "/api/auth/login",
        data={"username": "tester", "password": "new-secret123"},
    )
    assert relogin_response.status_code == 200


@pytest.mark.asyncio
async def test_cog_test_session_stop_and_report_flow(client, db_session):
    from sqlalchemy import select

    from app.models.entities.user import CogTestBlindSpot, CogTestSession, CogTestSnapshot, CogTestTurn, ReviewSchedule

    tokens = await register_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    card = await create_model_card(client, headers, "Cog Card", "metacognition")

    create_session_response = await client.post(
        "/api/cog-test/sessions",
        json={"concept": "Memory Recall", "max_rounds": 2, "model_card_id": card["id"]},
        headers=headers,
    )
    assert create_session_response.status_code == 200
    session_id = create_session_response.json()["session_id"]

    list_sessions_response = await client.get("/api/cog-test/sessions", headers=headers)
    assert list_sessions_response.status_code == 200
    assert any(item["id"] == session_id and item["status"] == "active" for item in list_sessions_response.json())

    submit_turn_response = await client.post(
        f"/api/cog-test/sessions/{session_id}/turns",
        json={"text": "My current understanding is incomplete."},
        headers=headers,
    )
    assert submit_turn_response.status_code == 200

    session_result = await db_session.execute(select(CogTestSession).where(CogTestSession.id == session_id))
    session = session_result.scalar_one()
    turn = CogTestTurn(
        session_id=session_id,
        turn_index=1,
        round_number=1,
        role="guide",
        dialogue_text="Probe the edge case.",
        understanding_level="low",
    )
    db_session.add(turn)
    await db_session.flush()
    db_session.add(
        CogTestBlindSpot(
            session_id=session_id,
            turn_id=turn.id,
            category="gap",
            description="Confuses retrieval strength with storage strength.",
        )
    )
    db_session.add(
        CogTestSnapshot(
            session_id=session_id,
            round_number=1,
            understanding_score="0.33",
            blind_spot_count=1,
            snapshot_json="{}",
        )
    )
    await db_session.commit()

    stop_response = await client.post(
        f"/api/cog-test/sessions/{session_id}/stop",
        headers=headers,
    )
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"

    schedule_result = await db_session.execute(
        select(ReviewSchedule).where(ReviewSchedule.model_card_id == card["id"])
    )
    schedule = schedule_result.scalar_one_or_none()
    assert schedule is not None
    assert schedule.interval_days == 1

    report_response = await client.get(
        f"/api/cog-test/sessions/{session_id}/report",
        headers=headers,
    )
    assert report_response.status_code == 200
    assert report_response.headers["content-type"].startswith("text/markdown")
    report_body = report_response.text
    assert "Memory Recall" in report_body
    assert "Confuses retrieval strength with storage strength." in report_body
