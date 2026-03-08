"""add learning modes and problem turns

Revision ID: 008
Revises: 007
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "problems",
        sa.Column("learning_mode", sa.String(length=20), nullable=False, server_default="socratic"),
    )

    op.add_column(
        "problem_responses",
        sa.Column("learning_mode", sa.String(length=20), nullable=False, server_default="socratic"),
    )
    op.add_column(
        "problem_responses",
        sa.Column("mode_metadata", sa.JSON(), nullable=True),
    )

    op.create_table(
        "problem_turns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=36), nullable=False),
        sa.Column("learning_mode", sa.String(length=20), nullable=False, server_default="socratic"),
        sa.Column("step_index", sa.Integer(), nullable=True),
        sa.Column("user_text", sa.Text(), nullable=True),
        sa.Column("assistant_text", sa.Text(), nullable=True),
        sa.Column("mode_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_problem_turns_user_id"), "problem_turns", ["user_id"], unique=False)
    op.create_index(op.f("ix_problem_turns_problem_id"), "problem_turns", ["problem_id"], unique=False)
    op.create_index(op.f("ix_problem_turns_learning_mode"), "problem_turns", ["learning_mode"], unique=False)
    op.create_index(op.f("ix_problem_turns_created_at"), "problem_turns", ["created_at"], unique=False)

    op.add_column(
        "problem_concept_candidates",
        sa.Column("learning_mode", sa.String(length=20), nullable=False, server_default="socratic"),
    )
    op.add_column(
        "problem_concept_candidates",
        sa.Column("source_turn_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        op.f("ix_problem_concept_candidates_learning_mode"),
        "problem_concept_candidates",
        ["learning_mode"],
        unique=False,
    )
    op.create_index(
        op.f("ix_problem_concept_candidates_source_turn_id"),
        "problem_concept_candidates",
        ["source_turn_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_problem_concept_candidates_source_turn_id_problem_turns",
        "problem_concept_candidates",
        "problem_turns",
        ["source_turn_id"],
        ["id"],
    )

    op.add_column(
        "learning_events",
        sa.Column("learning_mode", sa.String(length=20), nullable=True),
    )
    op.create_index(op.f("ix_learning_events_learning_mode"), "learning_events", ["learning_mode"], unique=False)

    op.execute("UPDATE problems SET learning_mode = 'socratic' WHERE learning_mode IS NULL")
    op.execute("UPDATE problem_responses SET learning_mode = 'socratic' WHERE learning_mode IS NULL")
    op.execute(
        """
        UPDATE problem_concept_candidates
        SET learning_mode = CASE
            WHEN source = 'ask' THEN 'exploration'
            ELSE 'socratic'
        END
        WHERE learning_mode IS NULL
        """
    )
    op.execute(
        """
        UPDATE learning_events
        SET learning_mode = CASE
            WHEN event_type = 'problem_inline_qa' THEN 'exploration'
            ELSE 'socratic'
        END
        WHERE learning_mode IS NULL
        """
    )


def downgrade():
    op.drop_index(op.f("ix_learning_events_learning_mode"), table_name="learning_events")
    op.drop_column("learning_events", "learning_mode")

    op.drop_constraint(
        "fk_problem_concept_candidates_source_turn_id_problem_turns",
        "problem_concept_candidates",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_problem_concept_candidates_source_turn_id"),
        table_name="problem_concept_candidates",
    )
    op.drop_index(
        op.f("ix_problem_concept_candidates_learning_mode"),
        table_name="problem_concept_candidates",
    )
    op.drop_column("problem_concept_candidates", "source_turn_id")
    op.drop_column("problem_concept_candidates", "learning_mode")

    op.drop_index(op.f("ix_problem_turns_created_at"), table_name="problem_turns")
    op.drop_index(op.f("ix_problem_turns_learning_mode"), table_name="problem_turns")
    op.drop_index(op.f("ix_problem_turns_problem_id"), table_name="problem_turns")
    op.drop_index(op.f("ix_problem_turns_user_id"), table_name="problem_turns")
    op.drop_table("problem_turns")

    op.drop_column("problem_responses", "mode_metadata")
    op.drop_column("problem_responses", "learning_mode")

    op.drop_column("problems", "learning_mode")
