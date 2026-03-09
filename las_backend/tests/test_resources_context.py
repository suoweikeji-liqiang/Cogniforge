import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities.user import Problem, ProblemTurn


@pytest.mark.asyncio
async def test_create_problem_resource_with_turn_context(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user,
):
    problem = Problem(
        user_id=str(test_user.id),
        title="Resource Problem",
        associated_concepts=["recall"],
    )
    db_session.add(problem)
    await db_session.flush()

    turn = ProblemTurn(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        learning_mode="exploration",
        step_index=0,
        user_text="Why use recall?",
        assistant_text="Recall matters when misses are costly.",
        mode_metadata={"turn_source": "ask"},
    )
    db_session.add(turn)
    await db_session.commit()

    response = await client.post(
        "/api/resources/",
        headers=auth_headers,
        json={
            "url": "https://example.com/recall-guide",
            "title": "Recall guide",
            "problem_id": str(problem.id),
            "source_turn_id": str(turn.id),
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["problem_id"] == str(problem.id)
    assert data["source_turn_id"] == str(turn.id)
    assert data["title"] == "Recall guide"


@pytest.mark.asyncio
async def test_list_resources_filtered_by_problem(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user,
):
    first_problem = Problem(
        user_id=str(test_user.id),
        title="First Resource Problem",
        associated_concepts=[],
    )
    second_problem = Problem(
        user_id=str(test_user.id),
        title="Second Resource Problem",
        associated_concepts=[],
    )
    db_session.add_all([first_problem, second_problem])
    await db_session.commit()

    await client.post(
        "/api/resources/",
        headers=auth_headers,
        json={
            "url": "https://example.com/first",
            "title": "First resource",
            "problem_id": str(first_problem.id),
        },
    )
    await client.post(
        "/api/resources/",
        headers=auth_headers,
        json={
            "url": "https://example.com/second",
            "title": "Second resource",
            "problem_id": str(second_problem.id),
        },
    )

    response = await client.get(
        f"/api/resources/?problem_id={first_problem.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "First resource"
    assert data[0]["problem_id"] == str(first_problem.id)
