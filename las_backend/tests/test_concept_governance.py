"""
Concept Governance Workflow Tests
Tests for concept candidate accept/reject/rollback flows
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.entities.user import Problem, ProblemConceptCandidate


@pytest.mark.asyncio
async def test_concept_candidate_auto_accept_high_confidence(client: AsyncClient, auth_headers: dict, db: AsyncSession):
    """High confidence concepts should be auto-accepted"""
    problem_response = await client.post(
        "/api/problems/",
        headers=auth_headers,
        json={"title": "Test Problem", "description": "Test", "associated_concepts": []},
    )
    assert problem_response.status_code == 201
    problem_id = problem_response.json()["id"]

    response = await client.post(
        f"/api/problems/{problem_id}/responses",
        headers=auth_headers,
        json={"problem_id": problem_id, "user_response": "Machine learning uses algorithms"},
    )
    assert response.status_code == 200
    data = response.json()

    # Should have accepted concepts if confidence is high
    assert "accepted_concepts" in data
    assert isinstance(data["accepted_concepts"], list)


@pytest.mark.asyncio
async def test_list_concept_candidates_by_status(client: AsyncClient, auth_headers: dict, db: AsyncSession):
    """Should filter candidates by status"""
    problem_response = await client.post(
        "/api/problems/",
        headers=auth_headers,
        json={"title": "Test Problem", "associated_concepts": []},
    )
    problem_id = problem_response.json()["id"]

    # Generate some candidates
    await client.post(
        f"/api/problems/{problem_id}/responses",
        headers=auth_headers,
        json={"problem_id": problem_id, "user_response": "Test response"},
    )

    # List all candidates
    all_response = await client.get(
        f"/api/problems/{problem_id}/concept-candidates",
        headers=auth_headers,
    )
    assert all_response.status_code == 200

    # List pending only
    pending_response = await client.get(
        f"/api/problems/{problem_id}/concept-candidates?status=pending",
        headers=auth_headers,
    )
    assert pending_response.status_code == 200
    for candidate in pending_response.json():
        assert candidate["status"] == "pending"


@pytest.mark.asyncio
async def test_accept_concept_candidate(client: AsyncClient, auth_headers: dict, db: AsyncSession, test_user):
    """Accepting a candidate should update status and add to problem concepts"""
    problem = Problem(
        user_id=str(test_user.id),
        title="Test Problem",
        associated_concepts=["existing concept"],
    )
    db.add(problem)
    await db.flush()

    candidate = ProblemConceptCandidate(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        concept_text="new concept",
        normalized_text="new concept",
        source="response",
        confidence=0.7,
        status="pending",
    )
    db.add(candidate)
    await db.commit()

    response = await client.post(
        f"/api/problems/{problem.id}/concept-candidates/{candidate.id}/accept",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["candidate"]["status"] == "accepted"
    assert data["candidate"]["reviewed_at"] is not None
    assert "trace_id" in data

    await db.refresh(problem)
    assert "new concept" in problem.associated_concepts


@pytest.mark.asyncio
async def test_reject_concept_candidate(client: AsyncClient, auth_headers: dict, db: AsyncSession, test_user):
    """Rejecting a candidate should update status without adding to problem"""
    problem = Problem(
        user_id=str(test_user.id),
        title="Test Problem",
        associated_concepts=["existing"],
    )
    db.add(problem)
    await db.flush()

    candidate = ProblemConceptCandidate(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        concept_text="bad concept",
        normalized_text="bad concept",
        source="response",
        confidence=0.5,
        status="pending",
    )
    db.add(candidate)
    await db.commit()

    response = await client.post(
        f"/api/problems/{problem.id}/concept-candidates/{candidate.id}/reject",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["candidate"]["status"] == "rejected"
    assert data["candidate"]["reviewed_at"] is not None

    await db.refresh(problem)
    assert "bad concept" not in problem.associated_concepts


@pytest.mark.asyncio
async def test_rollback_accepted_concept(client: AsyncClient, auth_headers: dict, db: AsyncSession, test_user):
    """Rolling back should remove concept from problem and mark candidates as reverted"""
    problem = Problem(
        user_id=str(test_user.id),
        title="Test Problem",
        associated_concepts=["keep this", "remove this"],
    )
    db.add(problem)
    await db.flush()

    candidate = ProblemConceptCandidate(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        concept_text="remove this",
        normalized_text="remove this",
        source="response",
        confidence=0.9,
        status="accepted",
    )
    db.add(candidate)
    await db.commit()

    response = await client.post(
        f"/api/problems/{problem.id}/concepts/rollback",
        headers=auth_headers,
        json={"concept_text": "remove this", "reason": "incorrect"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["removed"] is True
    assert "remove this" not in data["associated_concepts"]
    assert "keep this" in data["associated_concepts"]

    await db.refresh(candidate)
    assert candidate.status == "reverted"


@pytest.mark.asyncio
async def test_concept_candidate_max_limit(client: AsyncClient, auth_headers: dict, db: AsyncSession):
    """Should respect PROBLEM_CONCEPT_MAX_CANDIDATES_PER_TURN limit"""
    problem_response = await client.post(
        "/api/problems/",
        headers=auth_headers,
        json={"title": "Test Problem", "associated_concepts": []},
    )
    problem_id = problem_response.json()["id"]

    response = await client.post(
        f"/api/problems/{problem_id}/responses",
        headers=auth_headers,
        json={"problem_id": problem_id, "user_response": "Very long response with many concepts"},
    )
    assert response.status_code == 200

    # Check that we don't exceed the limit
    candidates_response = await client.get(
        f"/api/problems/{problem_id}/concept-candidates",
        headers=auth_headers,
    )
    candidates = candidates_response.json()
    # Should be <= PROBLEM_CONCEPT_MAX_CANDIDATES_PER_TURN (default 5)
    assert len(candidates) <= 5
