"""
Concept Governance Workflow Tests
Tests for concept candidate accept/reject/rollback flows
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.entities.user import (
    ConceptAlias,
    EvolutionLog,
    LearningPath,
    ModelCard,
    Problem,
    ProblemConceptCandidate,
    ProblemTurn,
    ReviewSchedule,
)


@pytest.mark.asyncio
async def test_concept_candidate_auto_accept_high_confidence(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
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
async def test_list_concept_candidates_by_status(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
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
async def test_accept_concept_candidate(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_user):
    """Accepting a candidate should update status and add to problem concepts"""
    problem = Problem(
        user_id=str(test_user.id),
        title="Test Problem",
        associated_concepts=["existing concept"],
    )
    db_session.add(problem)
    await db_session.flush()

    candidate = ProblemConceptCandidate(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        concept_text="new concept",
        normalized_text="new concept",
        source="response",
        confidence=0.7,
        status="pending",
    )
    db_session.add(candidate)
    await db_session.commit()

    response = await client.post(
        f"/api/problems/{problem.id}/concept-candidates/{candidate.id}/accept",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["candidate"]["status"] == "accepted"
    assert data["candidate"]["reviewed_at"] is not None
    assert "trace_id" in data

    await db_session.refresh(problem)
    assert "new concept" in problem.associated_concepts


@pytest.mark.asyncio
async def test_promote_accepted_concept_candidate_to_model_card_and_schedule_review(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user,
):
    problem = Problem(
        user_id=str(test_user.id),
        title="Test Problem",
        associated_concepts=["existing concept"],
    )
    db_session.add(problem)
    await db_session.flush()

    branch_path = LearningPath(
        problem_id=str(problem.id),
        title="Threshold comparison branch",
        kind="branch",
        path_data=[
            {
                "step": 1,
                "concept": "precision threshold",
                "description": "Compare how the threshold changes precision and recall.",
                "resources": [],
            }
        ],
        current_step=0,
        is_active=True,
    )
    db_session.add(branch_path)
    await db_session.flush()

    turn = ProblemTurn(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        path_id=str(branch_path.id),
        learning_mode="socratic",
        step_index=1,
        user_text="I am still calibrating the threshold tradeoff.",
        assistant_text="Tighten your explanation of precision versus recall.",
        mode_metadata={"step_concept": "precision threshold"},
    )
    db_session.add(turn)
    await db_session.flush()

    candidate = ProblemConceptCandidate(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        concept_text="precision threshold",
        normalized_text="precision threshold",
        source="response",
        learning_mode="socratic",
        source_turn_id=str(turn.id),
        confidence=0.81,
        status="accepted",
        evidence_snippet="Precision changes with the decision threshold.",
    )
    db_session.add(candidate)
    await db_session.commit()

    promote_response = await client.post(
        f"/api/problems/{problem.id}/concept-candidates/{candidate.id}/promote",
        headers=auth_headers,
    )
    assert promote_response.status_code == 200
    promote_data = promote_response.json()
    assert promote_data["candidate"]["linked_model_card_id"] is not None
    assert promote_data["model_card"]["title"] == "precision threshold"
    assert promote_data["created_model_card"] is True
    assert promote_data["review_scheduled"] is False
    assert promote_data["model_card"]["lifecycle_stage"] == "active"
    assert promote_data["model_card"]["origin_type"] == "problem_concept_candidate"
    assert promote_data["model_card"]["origin_stage"] == "accepted_concept_candidate"
    assert promote_data["model_card"]["origin_problem_id"] == str(problem.id)
    assert promote_data["model_card"]["origin_problem_title"] == "Test Problem"
    assert promote_data["model_card"]["origin_concept_candidate_id"] == str(candidate.id)
    assert promote_data["model_card"]["origin_source_turn_id"] == str(turn.id)
    assert promote_data["model_card"]["origin_learning_mode"] == "socratic"
    assert promote_data["model_card"]["origin_concept_text"] == "precision threshold"

    model_card_result = await db_session.execute(
        select(ModelCard).where(ModelCard.id == promote_data["model_card"]["id"])
    )
    model_card = model_card_result.scalar_one_or_none()
    assert model_card is not None
    assert model_card.lifecycle_stage == "active"
    assert model_card.origin_type == "problem_concept_candidate"
    assert model_card.origin_stage == "accepted_concept_candidate"
    assert model_card.origin_problem_id == str(problem.id)
    assert model_card.origin_problem_title == "Test Problem"
    assert model_card.origin_concept_candidate_id == str(candidate.id)
    assert model_card.origin_source_turn_id == str(turn.id)
    assert model_card.origin_learning_mode == "socratic"
    assert model_card.origin_concept_text == "precision threshold"
    assert "Promoted from problem: Test Problem" in (model_card.user_notes or "")

    schedule_response = await client.post(
        f"/api/problems/{problem.id}/concept-candidates/{candidate.id}/schedule-review",
        headers=auth_headers,
    )
    assert schedule_response.status_code == 200
    schedule_data = schedule_response.json()
    assert schedule_data["candidate"]["linked_model_card_id"] == promote_data["model_card"]["id"]
    assert schedule_data["review_scheduled"] is True
    assert schedule_data["next_review_at"] is not None

    schedule_result = await db_session.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.user_id == str(test_user.id),
            ReviewSchedule.model_card_id == promote_data["model_card"]["id"],
        )
    )
    review_schedule = schedule_result.scalar_one_or_none()
    assert review_schedule is not None

    schedules_response = await client.get("/api/srs/schedules", headers=auth_headers)
    assert schedules_response.status_code == 200
    schedules = schedules_response.json()
    assert len(schedules) == 1
    assert schedules[0]["origin"]["problem_id"] == str(problem.id)
    assert schedules[0]["origin"]["problem_title"] == "Test Problem"
    assert schedules[0]["origin"]["concept_text"] == "precision threshold"
    assert schedules[0]["origin"]["source_turn_id"] == str(turn.id)
    assert schedules[0]["origin"]["source_step_index"] == 1
    assert schedules[0]["origin"]["source_step_concept"] == "precision threshold"
    assert schedules[0]["origin"]["source_path_id"] == str(branch_path.id)
    assert schedules[0]["origin"]["source_path_kind"] == "branch"
    assert schedules[0]["origin"]["source_path_title"] == "Threshold comparison branch"
    assert "calibrating the threshold tradeoff" in schedules[0]["origin"]["source_turn_preview"]
    assert schedules[0]["recall_state"] == "scheduled"
    assert schedules[0]["recommended_action"] == "complete_first_recall"
    assert schedules[0]["needs_reinforcement"] is False
    assert schedules[0]["reinforcement_target"] is None

    from datetime import datetime, timedelta

    review_schedule.next_review_at = datetime.utcnow() - timedelta(minutes=5)
    await db_session.commit()

    review_response = await client.post(
        f"/api/srs/review/{review_schedule.id}",
        params={"quality": 0},
        headers=auth_headers,
    )
    assert review_response.status_code == 200
    review_data = review_response.json()
    assert review_data["recall_state"] == "fragile"
    assert review_data["recommended_action"] == "revisit_workspace"
    assert review_data["needs_reinforcement"] is True
    assert review_data["reinforcement_target"]["problem_id"] == str(problem.id)
    assert review_data["reinforcement_target"]["concept_text"] == "precision threshold"
    assert review_data["reinforcement_target"]["resume_step_index"] == 1
    assert review_data["reinforcement_target"]["resume_step_concept"] == "precision threshold"
    assert review_data["reinforcement_target"]["resume_path_id"] == str(branch_path.id)
    assert review_data["reinforcement_target"]["resume_path_kind"] == "branch"
    assert review_data["reinforcement_target"]["resume_path_title"] == "Threshold comparison branch"

    evolution_result = await db_session.execute(
        select(EvolutionLog).where(
            EvolutionLog.model_id == promote_data["model_card"]["id"],
            EvolutionLog.action_taken == "recall_reinforcement",
        )
    )
    reinforcement_log = evolution_result.scalar_one_or_none()
    assert reinforcement_log is not None
    assert "precision threshold" in (reinforcement_log.reason_for_change or "")


@pytest.mark.asyncio
async def test_reject_concept_candidate(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_user):
    """Rejecting a candidate should update status without adding to problem"""
    problem = Problem(
        user_id=str(test_user.id),
        title="Test Problem",
        associated_concepts=["existing"],
    )
    db_session.add(problem)
    await db_session.flush()

    candidate = ProblemConceptCandidate(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        concept_text="bad concept",
        normalized_text="bad concept",
        source="response",
        confidence=0.5,
        status="pending",
    )
    db_session.add(candidate)
    await db_session.commit()

    response = await client.post(
        f"/api/problems/{problem.id}/concept-candidates/{candidate.id}/reject",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["candidate"]["status"] == "rejected"
    assert data["candidate"]["reviewed_at"] is not None

    await db_session.refresh(problem)
    assert "bad concept" not in problem.associated_concepts


@pytest.mark.asyncio
async def test_merge_concept_candidate_into_existing_concept(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user,
):
    """Merging should preserve the existing concept and attach the candidate as an alias."""
    problem = Problem(
        user_id=str(test_user.id),
        title="Test Problem",
        associated_concepts=["neural network"],
    )
    db_session.add(problem)
    await db_session.flush()

    turn = ProblemTurn(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        learning_mode="exploration",
        step_index=0,
        user_text="How is an MLP different from a neural network?",
        assistant_text="",
        mode_metadata={"turn_source": "ask"},
    )
    db_session.add(turn)
    await db_session.flush()

    candidate = ProblemConceptCandidate(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        concept_text="MLP",
        normalized_text="mlp",
        source="ask",
        learning_mode="exploration",
        source_turn_id=str(turn.id),
        confidence=0.72,
        status="pending",
        evidence_snippet="The learner compared MLP with neural network.",
    )
    db_session.add(candidate)
    await db_session.commit()

    response = await client.post(
        f"/api/problems/{problem.id}/concept-candidates/{candidate.id}/merge",
        headers=auth_headers,
        json={"target_concept_text": "neural network"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["candidate"]["status"] == "merged"
    assert data["candidate"]["merged_into_concept"] == "neural network"
    assert data["candidate"]["source_turn_preview"].startswith("How is an MLP different")

    alias_result = await db_session.execute(
        select(ConceptAlias).where(ConceptAlias.normalized_alias == "mlp")
    )
    alias = alias_result.scalar_one_or_none()
    assert alias is not None

    await db_session.refresh(problem)
    assert "neural network" in problem.associated_concepts
    assert "MLP" not in problem.associated_concepts


@pytest.mark.asyncio
async def test_postpone_concept_candidate(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_user):
    """Postponing a candidate should keep it visible with postponed status."""
    problem = Problem(
        user_id=str(test_user.id),
        title="Test Problem",
        associated_concepts=["existing"],
    )
    db_session.add(problem)
    await db_session.flush()

    candidate = ProblemConceptCandidate(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        concept_text="uncertain concept",
        normalized_text="uncertain concept",
        source="response",
        learning_mode="socratic",
        confidence=0.44,
        status="pending",
    )
    db_session.add(candidate)
    await db_session.commit()

    response = await client.post(
        f"/api/problems/{problem.id}/concept-candidates/{candidate.id}/postpone",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["candidate"]["status"] == "postponed"
    assert data["candidate"]["reviewed_at"] is not None

    await db_session.refresh(candidate)
    assert candidate.status == "postponed"


@pytest.mark.asyncio
async def test_rollback_accepted_concept(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_user):
    """Rolling back should remove concept from problem and mark candidates as reverted"""
    problem = Problem(
        user_id=str(test_user.id),
        title="Test Problem",
        associated_concepts=["keep this", "remove this"],
    )
    db_session.add(problem)
    await db_session.flush()

    candidate = ProblemConceptCandidate(
        user_id=str(test_user.id),
        problem_id=str(problem.id),
        concept_text="remove this",
        normalized_text="remove this",
        source="response",
        confidence=0.9,
        status="accepted",
    )
    db_session.add(candidate)
    await db_session.commit()

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

    await db_session.refresh(candidate)
    assert candidate.status == "reverted"


@pytest.mark.asyncio
async def test_list_concept_candidates_includes_source_turn_preview(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Listing candidates should surface source mode and source turn preview for the workspace panel."""
    problem_response = await client.post(
        "/api/problems/",
        headers=auth_headers,
        json={"title": "Test Problem", "associated_concepts": []},
    )
    problem_id = problem_response.json()["id"]

    submit_response = await client.post(
        f"/api/problems/{problem_id}/responses",
        headers=auth_headers,
        json={"problem_id": problem_id, "user_response": "I think gradient descent updates the weights."},
    )
    assert submit_response.status_code == 200

    candidates_response = await client.get(
        f"/api/problems/{problem_id}/concept-candidates",
        headers=auth_headers,
    )
    assert candidates_response.status_code == 200
    candidates = candidates_response.json()
    assert candidates
    assert any(candidate["learning_mode"] == "socratic" for candidate in candidates)
    assert any(candidate.get("source_turn_preview") for candidate in candidates)


@pytest.mark.asyncio
async def test_concept_candidate_max_limit(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
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
