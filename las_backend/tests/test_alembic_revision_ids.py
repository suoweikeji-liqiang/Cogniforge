import re
from pathlib import Path


REVISION_RE = re.compile(r'^revision = "([^"]+)"$', re.MULTILINE)
DOWN_REVISION_RE = re.compile(r'^down_revision = (?:"([^"]+)"|None)$', re.MULTILINE)


def test_alembic_revision_ids_fit_version_table_limit():
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    revision_ids = {}

    for path in sorted(versions_dir.glob("*.py")):
        source = path.read_text()
        revision_match = REVISION_RE.search(source)
        down_revision_match = DOWN_REVISION_RE.search(source)

        assert revision_match is not None, f"Missing revision in {path.name}"
        assert down_revision_match is not None, f"Missing down_revision in {path.name}"

        revision = revision_match.group(1)
        down_revision = down_revision_match.group(1)

        assert len(revision) <= 32, f"{path.name} revision '{revision}' exceeds Alembic varchar(32) limit"
        assert revision not in revision_ids, f"Duplicate revision '{revision}' in {path.name}"

        revision_ids[revision] = {"path": path.name, "down_revision": down_revision}

    for revision, metadata in revision_ids.items():
        down_revision = metadata["down_revision"]
        if down_revision is not None:
            assert down_revision in revision_ids, (
                f"{metadata['path']} references unknown down_revision '{down_revision}'"
            )
