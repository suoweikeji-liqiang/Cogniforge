"""
API Contract Tests - Button-triggered Endpoints
Based on: .agents/skills/api-contract
"""

import pytest


@pytest.mark.asyncio
async def test_review_generate_request_validation(client, auth_headers):
    """AC-01: POST /reviews/generate - Request validation"""
    response = await client.post("/api/reviews/generate",
        headers=auth_headers,
        json={"review_type": "daily", "period": "2026-03-06"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "content" in data


@pytest.mark.asyncio
async def test_review_generate_missing_fields(client, auth_headers):
    """AC-02: POST /reviews/generate - Missing required fields"""
    response = await client.post("/api/reviews/generate",
        headers=auth_headers,
        json={}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_problem_create(client, auth_headers):
    """AC-04: POST /problems/ - Create problem"""
    response = await client.post("/api/problems/",
        headers=auth_headers,
        json={"title": "Test Problem", "description": "Test"}
    )
    assert response.status_code == 201  # API returns 201 Created
    data = response.json()
    assert data["title"] == "Test Problem"


@pytest.mark.asyncio
async def test_problems_list(client, auth_headers):
    """AC-05: GET /problems/ - Backward compatibility"""
    response = await client.get("/api/problems/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
