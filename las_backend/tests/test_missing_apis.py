"""
Tests for missing API endpoints
"""

import pytest


@pytest.mark.asyncio
async def test_notes_create_and_list(client, auth_headers):
    """Test notes API - create and list"""
    response = await client.post("/api/notes/",
        headers=auth_headers,
        json={"title": "Test Note", "content": "Note content"}
    )
    assert response.status_code == 201

    list_response = await client.get("/api/notes/", headers=auth_headers)
    assert list_response.status_code == 200


@pytest.mark.asyncio
async def test_statistics_overview(client, auth_headers):
    """Test statistics API"""
    response = await client.get("/api/statistics/overview", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_problems" in data or "problems" in data
