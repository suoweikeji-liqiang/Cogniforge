"""
Data Integrity Tests
Based on: .agents/skills/data-integrity
"""

import pytest
from sqlalchemy import select
from app.models.entities.user import Problem


@pytest.mark.asyncio
async def test_problem_required_fields(db_session, test_user):
    """DI-01-01: Problem requires title"""
    problem = Problem(user_id=test_user.id, description="Test")
    db_session.add(problem)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_problem_status_transitions(db_session, test_problem):
    """DI-02-01: Valid problem status transitions"""
    test_problem.status = "in_progress"
    await db_session.commit()
    assert test_problem.status == "in_progress"


@pytest.mark.asyncio
async def test_cascade_delete_user_problems(db_session, test_user):
    """DI-03-01: Deleting user cascades to problems"""
    problem = Problem(user_id=test_user.id, title="Test", description="Test")
    db_session.add(problem)
    await db_session.commit()
    problem_id = problem.id

    await db_session.delete(test_user)
    await db_session.commit()

    result = await db_session.execute(select(Problem).where(Problem.id == problem_id))
    assert result.scalar_one_or_none() is None
