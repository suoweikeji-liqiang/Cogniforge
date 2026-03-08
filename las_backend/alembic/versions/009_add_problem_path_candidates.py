"""add problem path candidates

Revision ID: 009
Revises: 008
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "problem_path_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=36), nullable=False),
        sa.Column("learning_mode", sa.String(length=20), nullable=False, server_default="socratic"),
        sa.Column("source_turn_id", sa.String(length=36), nullable=True),
        sa.Column("step_index", sa.Integer(), nullable=True),
        sa.Column("path_type", sa.String(length=30), nullable=False, server_default="branch_deep_dive"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("normalized_title", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("recommended_insertion", sa.String(length=40), nullable=False, server_default="save_as_side_branch"),
        sa.Column("selected_insertion", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("evidence_snippet", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"]),
        sa.ForeignKeyConstraint(["source_turn_id"], ["problem_turns.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_problem_path_candidates_user_id"), "problem_path_candidates", ["user_id"], unique=False)
    op.create_index(op.f("ix_problem_path_candidates_problem_id"), "problem_path_candidates", ["problem_id"], unique=False)
    op.create_index(op.f("ix_problem_path_candidates_learning_mode"), "problem_path_candidates", ["learning_mode"], unique=False)
    op.create_index(op.f("ix_problem_path_candidates_source_turn_id"), "problem_path_candidates", ["source_turn_id"], unique=False)
    op.create_index(op.f("ix_problem_path_candidates_path_type"), "problem_path_candidates", ["path_type"], unique=False)
    op.create_index(op.f("ix_problem_path_candidates_normalized_title"), "problem_path_candidates", ["normalized_title"], unique=False)
    op.create_index(op.f("ix_problem_path_candidates_status"), "problem_path_candidates", ["status"], unique=False)
    op.create_index(op.f("ix_problem_path_candidates_created_at"), "problem_path_candidates", ["created_at"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_problem_path_candidates_created_at"), table_name="problem_path_candidates")
    op.drop_index(op.f("ix_problem_path_candidates_status"), table_name="problem_path_candidates")
    op.drop_index(op.f("ix_problem_path_candidates_normalized_title"), table_name="problem_path_candidates")
    op.drop_index(op.f("ix_problem_path_candidates_path_type"), table_name="problem_path_candidates")
    op.drop_index(op.f("ix_problem_path_candidates_source_turn_id"), table_name="problem_path_candidates")
    op.drop_index(op.f("ix_problem_path_candidates_learning_mode"), table_name="problem_path_candidates")
    op.drop_index(op.f("ix_problem_path_candidates_problem_id"), table_name="problem_path_candidates")
    op.drop_index(op.f("ix_problem_path_candidates_user_id"), table_name="problem_path_candidates")
    op.drop_table("problem_path_candidates")
