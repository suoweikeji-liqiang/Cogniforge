"""add model card origin fields

Revision ID: 016
Revises: 015
Create Date: 2026-03-10 16:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_cards") as batch_op:
        batch_op.add_column(
            sa.Column("origin_type", sa.String(length=40), nullable=False, server_default="manual"),
        )
        batch_op.add_column(
            sa.Column(
                "origin_stage",
                sa.String(length=50),
                nullable=False,
                server_default="manual_creation",
            ),
        )
        batch_op.add_column(sa.Column("origin_problem_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("origin_problem_title", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("origin_concept_candidate_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("origin_source_turn_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("origin_learning_mode", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("origin_concept_text", sa.String(length=120), nullable=True))
        batch_op.create_index("ix_model_cards_origin_type", ["origin_type"], unique=False)
        batch_op.create_index("ix_model_cards_origin_stage", ["origin_stage"], unique=False)
        batch_op.create_index("ix_model_cards_origin_problem_id", ["origin_problem_id"], unique=False)
        batch_op.create_index(
            "ix_model_cards_origin_concept_candidate_id",
            ["origin_concept_candidate_id"],
            unique=False,
        )
        batch_op.create_index("ix_model_cards_origin_source_turn_id", ["origin_source_turn_id"], unique=False)
        batch_op.create_index("ix_model_cards_origin_learning_mode", ["origin_learning_mode"], unique=False)
        batch_op.create_foreign_key(
            "fk_model_cards_origin_problem_id_problems",
            "problems",
            ["origin_problem_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_model_cards_origin_source_turn_id_problem_turns",
            "problem_turns",
            ["origin_source_turn_id"],
            ["id"],
        )

    op.execute("UPDATE model_cards SET origin_type = 'manual' WHERE origin_type IS NULL")
    op.execute("UPDATE model_cards SET origin_stage = 'manual_creation' WHERE origin_stage IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("model_cards") as batch_op:
        batch_op.drop_constraint("fk_model_cards_origin_source_turn_id_problem_turns", type_="foreignkey")
        batch_op.drop_constraint("fk_model_cards_origin_problem_id_problems", type_="foreignkey")
        batch_op.drop_index("ix_model_cards_origin_learning_mode")
        batch_op.drop_index("ix_model_cards_origin_source_turn_id")
        batch_op.drop_index("ix_model_cards_origin_concept_candidate_id")
        batch_op.drop_index("ix_model_cards_origin_problem_id")
        batch_op.drop_index("ix_model_cards_origin_stage")
        batch_op.drop_index("ix_model_cards_origin_type")
        batch_op.drop_column("origin_concept_text")
        batch_op.drop_column("origin_learning_mode")
        batch_op.drop_column("origin_source_turn_id")
        batch_op.drop_column("origin_concept_candidate_id")
        batch_op.drop_column("origin_problem_title")
        batch_op.drop_column("origin_problem_id")
        batch_op.drop_column("origin_stage")
        batch_op.drop_column("origin_type")
