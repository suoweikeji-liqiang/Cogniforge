"""add resource context fields

Revision ID: 014_add_resource_context_fields
Revises: 013_add_note_context_fields
Create Date: 2026-03-08 17:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "014_add_resource_context_fields"
down_revision = "013_add_note_context_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resource_links", sa.Column("problem_id", sa.String(length=36), nullable=True))
    op.add_column("resource_links", sa.Column("source_turn_id", sa.String(length=36), nullable=True))
    op.create_index("ix_resource_links_problem_id", "resource_links", ["problem_id"], unique=False)
    op.create_index("ix_resource_links_source_turn_id", "resource_links", ["source_turn_id"], unique=False)
    op.create_foreign_key(
        "fk_resource_links_problem_id_problems",
        "resource_links",
        "problems",
        ["problem_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_resource_links_source_turn_id_problem_turns",
        "resource_links",
        "problem_turns",
        ["source_turn_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_resource_links_source_turn_id_problem_turns", "resource_links", type_="foreignkey")
    op.drop_constraint("fk_resource_links_problem_id_problems", "resource_links", type_="foreignkey")
    op.drop_index("ix_resource_links_source_turn_id", table_name="resource_links")
    op.drop_index("ix_resource_links_problem_id", table_name="resource_links")
    op.drop_column("resource_links", "source_turn_id")
    op.drop_column("resource_links", "problem_id")
