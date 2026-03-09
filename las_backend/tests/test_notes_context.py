import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities.user import Problem, ProblemTurn


@pytest.mark.asyncio
async def test_create_problem_note_with_turn_context(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user,
):
    problem = Problem(
        user_id=str(test_user.id),
        title="Notes Problem",
        associated_concepts=["precision"],
    )
    db_session.add(problem)
    await db_session.flush()

    turn = ProblemTurn(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        learning_mode="exploration",
        step_index=0,
        user_text="What is precision?",
        assistant_text="Precision is...",
        mode_metadata={"turn_source": "ask"},
    )
    db_session.add(turn)
    await db_session.commit()

    response = await client.post(
        "/api/notes/",
        headers=auth_headers,
        json={
            "content": "Keep this attached to the precision question.",
            "tags": ["precision"],
            "problem_id": str(problem.id),
            "source_turn_id": str(turn.id),
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["problem_id"] == str(problem.id)
    assert data["source_turn_id"] == str(turn.id)
    assert data["tags"] == ["precision"]


@pytest.mark.asyncio
async def test_list_notes_filtered_by_problem(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user,
):
    first_problem = Problem(
        user_id=str(test_user.id),
        title="First Problem",
        associated_concepts=[],
    )
    second_problem = Problem(
        user_id=str(test_user.id),
        title="Second Problem",
        associated_concepts=[],
    )
    db_session.add_all([first_problem, second_problem])
    await db_session.commit()

    await client.post(
        "/api/notes/",
        headers=auth_headers,
        json={
            "content": "Note for first problem",
            "problem_id": str(first_problem.id),
        },
    )
    await client.post(
        "/api/notes/",
        headers=auth_headers,
        json={
            "content": "Note for second problem",
            "problem_id": str(second_problem.id),
        },
    )

    response = await client.get(
        f"/api/notes/?problem_id={first_problem.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["content"] == "Note for first problem"
    assert data[0]["problem_id"] == str(first_problem.id)
