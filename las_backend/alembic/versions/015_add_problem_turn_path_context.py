"""add problem turn path context

Revision ID: 015
Revises: 014
Create Date: 2026-03-09 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("problem_turns") as batch_op:
        batch_op.add_column(sa.Column("path_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_problem_turns_path_id", ["path_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_problem_turns_path_id_learning_paths",
            "learning_paths",
            ["path_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("problem_turns") as batch_op:
        batch_op.drop_constraint("fk_problem_turns_path_id_learning_paths", type_="foreignkey")
        batch_op.drop_index("ix_problem_turns_path_id")
        batch_op.drop_column("path_id")
