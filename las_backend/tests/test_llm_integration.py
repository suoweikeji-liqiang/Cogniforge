"""
LLM Integration Tests with Real API Calls
Requires test.env with QWEN_API_KEY
"""

import pytest
import os


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("QWEN_API_KEY"), reason="Requires QWEN_API_KEY")
async def test_problem_response_with_real_llm(client, auth_headers):
    """Test complete problem response flow with real LLM"""
    # Create problem
    problem_response = await client.post("/api/problems/",
        headers=auth_headers,
        json={
            "title": "向量检索原理",
            "description": "理解向量检索和语义搜索",
            "associated_concepts": ["向量", "检索"]
        }
    )
    assert problem_response.status_code == 201
    problem = problem_response.json()

    # Submit response with real LLM evaluation
    response = await client.post(
        f"/api/problems/{problem['id']}/responses",
        headers=auth_headers,
        json={
            "problem_id": problem["id"],
            "user_response": "向量检索使用余弦相似度计算语义相关性"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "structured_feedback" in data
    assert data["llm_calls"] > 0


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("QWEN_API_KEY"), reason="Requires QWEN_API_KEY")
async def test_conversation_with_real_llm(client, auth_headers):
    """Test conversation with real LLM response"""
    # Create conversation
    conv_response = await client.post("/api/conversations/",
        headers=auth_headers,
        json={"title": "测试对话"}
    )
    assert conv_response.status_code == 201
    conv = conv_response.json()

    # Chat with real LLM
    chat_response = await client.post("/api/conversations/chat",
        headers=auth_headers,
        json={
            "conversation_id": conv["id"],
            "message": "什么是向量检索？"
        }
    )

    assert chat_response.status_code == 200
    data = chat_response.json()
    assert data["message"]
    assert len(data["message"]) > 10
