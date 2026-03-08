"""support multi learning paths

Revision ID: 010
Revises: 009
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("learning_paths") as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("kind", sa.String(length=20), nullable=False, server_default="main"))
        batch_op.add_column(sa.Column("parent_path_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("source_turn_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("return_step_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("branch_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.drop_constraint(None, type_="unique")
        batch_op.create_index(op.f("ix_learning_paths_problem_id"), ["problem_id"], unique=False)
        batch_op.create_index(op.f("ix_learning_paths_kind"), ["kind"], unique=False)
        batch_op.create_index(op.f("ix_learning_paths_parent_path_id"), ["parent_path_id"], unique=False)
        batch_op.create_index(op.f("ix_learning_paths_source_turn_id"), ["source_turn_id"], unique=False)
        batch_op.create_index(op.f("ix_learning_paths_is_active"), ["is_active"], unique=False)
        batch_op.create_foreign_key(
            "fk_learning_paths_parent_path_id_learning_paths",
            "learning_paths",
            ["parent_path_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_learning_paths_source_turn_id_problem_turns",
            "problem_turns",
            ["source_turn_id"],
            ["id"],
        )

    op.execute(
        """
        UPDATE learning_paths
        SET title = (
            SELECT problems.title
            FROM problems
            WHERE problems.id = learning_paths.problem_id
        )
        WHERE title IS NULL
        """
    )
    op.execute("UPDATE learning_paths SET kind = 'main' WHERE kind IS NULL")
    op.execute("UPDATE learning_paths SET is_active = 1 WHERE is_active IS NULL")


def downgrade():
    with op.batch_alter_table("learning_paths") as batch_op:
        batch_op.drop_constraint("fk_learning_paths_source_turn_id_problem_turns", type_="foreignkey")
        batch_op.drop_constraint("fk_learning_paths_parent_path_id_learning_paths", type_="foreignkey")
        batch_op.drop_index(op.f("ix_learning_paths_is_active"))
        batch_op.drop_index(op.f("ix_learning_paths_source_turn_id"))
        batch_op.drop_index(op.f("ix_learning_paths_parent_path_id"))
        batch_op.drop_index(op.f("ix_learning_paths_kind"))
        batch_op.drop_index(op.f("ix_learning_paths_problem_id"))
        batch_op.create_unique_constraint(None, ["problem_id"])
        batch_op.drop_column("is_active")
        batch_op.drop_column("branch_reason")
        batch_op.drop_column("return_step_id")
        batch_op.drop_column("source_turn_id")
        batch_op.drop_column("parent_path_id")
        batch_op.drop_column("kind")
        batch_op.drop_column("title")
