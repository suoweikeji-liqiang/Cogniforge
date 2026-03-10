import sys
import types
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_migration_module():
    module_name = "test_migration_010_support_multi_learning_paths"
    module_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "010_support_multi_learning_paths.py"
    spec = spec_from_file_location(module_name, module_path)
    module = module_from_spec(spec)

    alembic_module = types.ModuleType("alembic")
    alembic_module.op = types.SimpleNamespace()
    original_alembic = sys.modules.get("alembic")
    sys.modules["alembic"] = alembic_module

    try:
        assert spec.loader is not None
        spec.loader.exec_module(module)
    finally:
        if original_alembic is None:
            del sys.modules["alembic"]
        else:
            sys.modules["alembic"] = original_alembic

    return module


def test_drop_learning_paths_problem_id_unique_constraint_uses_reflected_name(monkeypatch):
    migration = _load_migration_module()
    dropped = []

    class FakeInspector:
        def get_unique_constraints(self, table_name):
            assert table_name == "learning_paths"
            return [
                {"name": "learning_paths_problem_id_key", "column_names": ["problem_id"]},
                {"name": "uq_other", "column_names": ["other_column"]},
            ]

    monkeypatch.setattr(migration.op, "get_bind", lambda: object(), raising=False)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: FakeInspector())
    monkeypatch.setattr(
        migration.op,
        "drop_constraint",
        lambda name, table_name, type_: dropped.append((name, table_name, type_)),
        raising=False,
    )

    migration._drop_learning_paths_problem_id_unique_constraint()

    assert dropped == [("learning_paths_problem_id_key", "learning_paths", "unique")]


def test_drop_learning_paths_problem_id_unique_constraint_noops_when_missing(monkeypatch):
    migration = _load_migration_module()
    dropped = []

    class FakeInspector:
        def get_unique_constraints(self, table_name):
            assert table_name == "learning_paths"
            return [{"name": "uq_other", "column_names": ["other_column"]}]

    monkeypatch.setattr(migration.op, "get_bind", lambda: object(), raising=False)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: FakeInspector())
    monkeypatch.setattr(
        migration.op,
        "drop_constraint",
        lambda name, table_name, type_: dropped.append((name, table_name, type_)),
        raising=False,
    )

    migration._drop_learning_paths_problem_id_unique_constraint()

    assert dropped == []
