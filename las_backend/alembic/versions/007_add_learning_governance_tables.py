"""add learning governance tables

Revision ID: 007
Revises: 006
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "problem_mastery_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=36), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mastery_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pass_stage", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("auto_advanced", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("correctness_label", sa.String(length=100), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_problem_mastery_events_user_id"), "problem_mastery_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_problem_mastery_events_problem_id"), "problem_mastery_events", ["problem_id"], unique=False)
    op.create_index(op.f("ix_problem_mastery_events_created_at"), "problem_mastery_events", ["created_at"], unique=False)

    op.create_table(
        "problem_concept_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=36), nullable=False),
        sa.Column("concept_text", sa.String(length=120), nullable=False),
        sa.Column("normalized_text", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="response"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("evidence_snippet", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_problem_concept_candidates_user_id"), "problem_concept_candidates", ["user_id"], unique=False)
    op.create_index(op.f("ix_problem_concept_candidates_problem_id"), "problem_concept_candidates", ["problem_id"], unique=False)
    op.create_index(op.f("ix_problem_concept_candidates_normalized_text"), "problem_concept_candidates", ["normalized_text"], unique=False)
    op.create_index(op.f("ix_problem_concept_candidates_status"), "problem_concept_candidates", ["status"], unique=False)
    op.create_index(op.f("ix_problem_concept_candidates_created_at"), "problem_concept_candidates", ["created_at"], unique=False)

    op.create_table(
        "concepts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=True, server_default="auto"),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_concepts_user_normalized_name"),
    )
    op.create_index(op.f("ix_concepts_user_id"), "concepts", ["user_id"], unique=False)
    op.create_index(op.f("ix_concepts_normalized_name"), "concepts", ["normalized_name"], unique=False)

    op.create_table(
        "concept_aliases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("concept_id", sa.String(length=36), nullable=False),
        sa.Column("alias", sa.String(length=120), nullable=False),
        sa.Column("normalized_alias", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_id", "normalized_alias", name="uq_concept_aliases_concept_alias"),
    )
    op.create_index(op.f("ix_concept_aliases_concept_id"), "concept_aliases", ["concept_id"], unique=False)
    op.create_index(op.f("ix_concept_aliases_normalized_alias"), "concept_aliases", ["normalized_alias"], unique=False)

    op.create_table(
        "concept_relations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("source_concept_id", sa.String(length=36), nullable=False),
        sa.Column("target_concept_id", sa.String(length=36), nullable=False),
        sa.Column("relation_type", sa.String(length=50), nullable=False, server_default="related"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["source_concept_id"], ["concepts.id"]),
        sa.ForeignKeyConstraint(["target_concept_id"], ["concepts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_concept_relations_user_id"), "concept_relations", ["user_id"], unique=False)
    op.create_index(op.f("ix_concept_relations_source_concept_id"), "concept_relations", ["source_concept_id"], unique=False)
    op.create_index(op.f("ix_concept_relations_target_concept_id"), "concept_relations", ["target_concept_id"], unique=False)

    op.create_table(
        "concept_evidences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("concept_id", sa.String(length=36), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_concept_evidences_user_id"), "concept_evidences", ["user_id"], unique=False)
    op.create_index(op.f("ix_concept_evidences_concept_id"), "concept_evidences", ["concept_id"], unique=False)

    op.create_table(
        "learning_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("trace_id", sa.String(length=36), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learning_events_user_id"), "learning_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_learning_events_problem_id"), "learning_events", ["problem_id"], unique=False)
    op.create_index(op.f("ix_learning_events_event_type"), "learning_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_learning_events_trace_id"), "learning_events", ["trace_id"], unique=False)
    op.create_index(op.f("ix_learning_events_created_at"), "learning_events", ["created_at"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_learning_events_created_at"), table_name="learning_events")
    op.drop_index(op.f("ix_learning_events_trace_id"), table_name="learning_events")
    op.drop_index(op.f("ix_learning_events_event_type"), table_name="learning_events")
    op.drop_index(op.f("ix_learning_events_problem_id"), table_name="learning_events")
    op.drop_index(op.f("ix_learning_events_user_id"), table_name="learning_events")
    op.drop_table("learning_events")

    op.drop_index(op.f("ix_concept_evidences_concept_id"), table_name="concept_evidences")
    op.drop_index(op.f("ix_concept_evidences_user_id"), table_name="concept_evidences")
    op.drop_table("concept_evidences")

    op.drop_index(op.f("ix_concept_relations_target_concept_id"), table_name="concept_relations")
    op.drop_index(op.f("ix_concept_relations_source_concept_id"), table_name="concept_relations")
    op.drop_index(op.f("ix_concept_relations_user_id"), table_name="concept_relations")
    op.drop_table("concept_relations")

    op.drop_index(op.f("ix_concept_aliases_normalized_alias"), table_name="concept_aliases")
    op.drop_index(op.f("ix_concept_aliases_concept_id"), table_name="concept_aliases")
    op.drop_table("concept_aliases")

    op.drop_index(op.f("ix_concepts_normalized_name"), table_name="concepts")
    op.drop_index(op.f("ix_concepts_user_id"), table_name="concepts")
    op.drop_table("concepts")

    op.drop_index(op.f("ix_problem_concept_candidates_created_at"), table_name="problem_concept_candidates")
    op.drop_index(op.f("ix_problem_concept_candidates_status"), table_name="problem_concept_candidates")
    op.drop_index(op.f("ix_problem_concept_candidates_normalized_text"), table_name="problem_concept_candidates")
    op.drop_index(op.f("ix_problem_concept_candidates_problem_id"), table_name="problem_concept_candidates")
    op.drop_index(op.f("ix_problem_concept_candidates_user_id"), table_name="problem_concept_candidates")
    op.drop_table("problem_concept_candidates")

    op.drop_index(op.f("ix_problem_mastery_events_created_at"), table_name="problem_mastery_events")
    op.drop_index(op.f("ix_problem_mastery_events_problem_id"), table_name="problem_mastery_events")
    op.drop_index(op.f("ix_problem_mastery_events_user_id"), table_name="problem_mastery_events")
    op.drop_table("problem_mastery_events")
