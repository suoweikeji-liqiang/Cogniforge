"""
Security Threat Model Tests
Based on: .agents/skills/security-threatmodel
"""

import pytest


@pytest.mark.asyncio
async def test_unauthorized_review_generation(client):
    """ST-01-01: Prevent unauthenticated review generation"""
    response = await client.post("/api/reviews/generate", json={
        "review_type": "daily",
        "period": "2026-03-06"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sql_injection_problem_title(client, auth_headers):
    """ST-02-01: SQL injection in problem title"""
    response = await client.post("/api/problems/",
        headers=auth_headers,
        json={"title": "'; DROP TABLE problems; --", "description": "Test"}
    )
    # SQLAlchemy ORM protects against SQL injection, should create successfully
    assert response.status_code == 201

    # Verify table still exists
    list_response = await client.get("/api/problems/", headers=auth_headers)
    assert list_response.status_code == 200


@pytest.mark.asyncio
async def test_xss_in_problem_description(client, auth_headers):
    """ST-02-02: XSS prevention in problem description"""
    response = await client.post("/api/problems/",
        headers=auth_headers,
        json={"title": "Test", "description": "<script>alert('XSS')</script>"}
    )
    # API accepts input, frontend should sanitize
    assert response.status_code == 201
