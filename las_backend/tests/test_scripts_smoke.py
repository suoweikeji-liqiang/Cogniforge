import importlib.util
from argparse import Namespace
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.database import Base
from app.models.entities.user import ModelCard, Problem, ResourceLink, User


def load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_backfill_embeddings_script_populates_all_supported_entities(db_session):
    user = User(
        email="embed@example.com",
        username="embedder",
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.flush()

    card = ModelCard(
        user_id=user.id,
        title="Backfill Card",
        user_notes="semantic lookup target",
        examples=["vector"],
        embedding=None,
    )
    problem = Problem(
        user_id=user.id,
        title="Backfill Problem",
        description="Needs better retrieval",
        associated_concepts=["search"],
        embedding=None,
    )
    resource = ResourceLink(
        user_id=user.id,
        url="https://example.com/retrieval",
        title="Retrieval Resource",
        embedding=None,
    )
    db_session.add_all([card, problem, resource])
    await db_session.commit()

    module = load_module(
        "backfill_model_card_embeddings",
        Path(__file__).resolve().parents[1] / "scripts" / "backfill_model_card_embeddings.py",
    )
    await module.main()

    await db_session.refresh(card)
    await db_session.refresh(problem)
    await db_session.refresh(resource)

    assert len(card.embedding) == 64
    assert len(problem.embedding) == 64
    assert len(resource.embedding) == 64


@pytest.mark.asyncio
async def test_sqlite_migration_script_copies_core_rows(tmp_path, monkeypatch):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    source_url = f"sqlite+aiosqlite:///{source_db}"
    target_url = f"sqlite+aiosqlite:///{target_db}"

    source_engine = create_async_engine(source_url, echo=False)
    target_engine = create_async_engine(target_url, echo=False)
    source_session_factory = async_sessionmaker(source_engine, expire_on_commit=False)
    target_session_factory = async_sessionmaker(target_engine, expire_on_commit=False)

    async with source_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with source_session_factory() as session:
        user = User(
            email="migrate@example.com",
            username="migrator",
            hashed_password="hashed",
        )
        session.add(user)
        await session.flush()

        card = ModelCard(
            user_id=user.id,
            title="Migrated Card",
            user_notes="from source sqlite",
            examples=["migration"],
        )
        problem = Problem(
            user_id=user.id,
            title="Migrated Problem",
            description="copied from sqlite",
            associated_concepts=["import"],
        )
        resource = ResourceLink(
            user_id=user.id,
            url="https://example.com/migrated",
            title="Migrated Resource",
        )
        session.add_all([card, problem, resource])
        await session.commit()

    module = load_module(
        "migrate_sqlite_to_postgres",
        Path(__file__).resolve().parents[1] / "scripts" / "migrate_sqlite_to_postgres.py",
    )
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: Namespace(
            source_sqlite=str(source_db),
            target_url=target_url,
            truncate_target=True,
        ),
    )

    await module.main()

    async with target_session_factory() as session:
        cards = (await session.execute(select(ModelCard))).scalars().all()
        problems = (await session.execute(select(Problem))).scalars().all()
        resources = (await session.execute(select(ResourceLink))).scalars().all()

    assert len(cards) == 1
    assert cards[0].title == "Migrated Card"
    assert len(problems) == 1
    assert problems[0].title == "Migrated Problem"
    assert len(resources) == 1
    assert resources[0].title == "Migrated Resource"

    await source_engine.dispose()
    await target_engine.dispose()
