"""add note context fields

Revision ID: 013
Revises: 012
Create Date: 2026-03-08 16:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quick_notes", sa.Column("problem_id", sa.String(length=36), nullable=True))
    op.add_column("quick_notes", sa.Column("source_turn_id", sa.String(length=36), nullable=True))
    op.create_index("ix_quick_notes_problem_id", "quick_notes", ["problem_id"], unique=False)
    op.create_index("ix_quick_notes_source_turn_id", "quick_notes", ["source_turn_id"], unique=False)
    op.create_foreign_key(
        "fk_quick_notes_problem_id_problems",
        "quick_notes",
        "problems",
        ["problem_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_quick_notes_source_turn_id_problem_turns",
        "quick_notes",
        "problem_turns",
        ["source_turn_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_quick_notes_source_turn_id_problem_turns", "quick_notes", type_="foreignkey")
    op.drop_constraint("fk_quick_notes_problem_id_problems", "quick_notes", type_="foreignkey")
    op.drop_index("ix_quick_notes_source_turn_id", table_name="quick_notes")
    op.drop_index("ix_quick_notes_problem_id", table_name="quick_notes")
    op.drop_column("quick_notes", "source_turn_id")
    op.drop_column("quick_notes", "problem_id")
