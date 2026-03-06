import os
import tempfile
from pathlib import Path
from typing import Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from dotenv import load_dotenv


# Load test.env if exists for real LLM tests
test_env_path = Path(__file__).parent.parent / "test.env"
if test_env_path.exists():
    load_dotenv(test_env_path)

_tmp_db = tempfile.NamedTemporaryFile(prefix="cogniforge-test-", suffix=".db", delete=False)
os.environ["DATABASE_FILE"] = _tmp_db.name
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key"

from app.main import app  # noqa: E402
from app.core.database import Base, engine, AsyncSessionLocal  # noqa: E402
from app.services.model_os_service import model_os_service  # noqa: E402
from app.services.cog_test_engine import _engines  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    _engines.clear()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="session", autouse=True)
def cleanup_temp_db(request):
    def _cleanup():
        Path(_tmp_db.name).unlink(missing_ok=True)

    request.addfinalizer(_cleanup)


@pytest_asyncio.fixture(autouse=True)
async def stub_llm(monkeypatch):
    async def fake_create_model_card(user_id: str, title: str, description: str, associated_concepts: list[str]):
        return {
            "concept_maps": {"nodes": [], "edges": []},
            "examples": associated_concepts or [title.lower()],
            "limitations": [f"edge case for {title}"],
        }

    async def fake_generate_learning_path(problem_title: str, problem_description: str, existing_knowledge: list[str]):
        return [
            {
                "step": 1,
                "concept": f"{problem_title} basics",
                "description": problem_description or "Learn the basics",
                "resources": [],
            }
        ]

    async def fake_generate_feedback_structured(user_response: str, concept: str, model_examples: list[str], retrieval_context: Optional[str] = None):
        return {
            "correctness": "partially correct",
            "misconceptions": ["test misconception"] if user_response else [],
            "suggestions": ["test suggestion"],
            "next_question": f"What is the boundary of {concept}?",
        }

    async def fake_generate(prompt: str, provider_type: Optional[str] = None, model_id: Optional[str] = None, **kwargs):
        return "stubbed response"

    async def fake_generate_with_context(
        prompt: str,
        context: list[dict],
        retrieval_context: Optional[str] = None,
        provider_type: Optional[str] = None,
        model_id: Optional[str] = None,
        **kwargs,
    ):
        return "stubbed contextual response"

    monkeypatch.setattr(model_os_service, "create_model_card", fake_create_model_card)
    monkeypatch.setattr(model_os_service, "generate_learning_path", fake_generate_learning_path)
    monkeypatch.setattr(model_os_service, "generate_feedback_structured", fake_generate_feedback_structured)
    monkeypatch.setattr(model_os_service.llm, "generate", fake_generate)
    monkeypatch.setattr(model_os_service.llm, "generate_with_context", fake_generate_with_context)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session):
    from app.models.entities.user import User
    from app.core.security import get_password_hash

    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password"),
        role="user"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user
    # Keep session open until test completes


@pytest_asyncio.fixture
async def admin_user(db_session):
    from app.models.entities.user import User
    from app.core.security import get_password_hash

    user = User(
        email="admin@example.com",
        username="admin",
        hashed_password=get_password_hash("password"),
        role="admin"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_token(client, test_user):
    response = await client.post("/api/auth/login", data={
        "username": "testuser",  # Use username, not email
        "password": "password"
    })
    assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
    data = response.json()
    return data["access_token"]


@pytest_asyncio.fixture
async def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest_asyncio.fixture
async def test_problem(db_session, test_user):
    from app.models.entities.user import Problem

    problem = Problem(
        user_id=test_user.id,
        title="Test Problem",
        description="Test description",
        status="new"
    )
    db_session.add(problem)
    await db_session.commit()
    await db_session.refresh(problem)
    return problem
