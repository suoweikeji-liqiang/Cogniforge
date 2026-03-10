"""link problem concept candidates to model cards

Revision ID: 012
Revises: 011
Create Date: 2026-03-08 15:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "problem_concept_candidates",
        sa.Column("linked_model_card_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_problem_concept_candidates_linked_model_card_id",
        "problem_concept_candidates",
        ["linked_model_card_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_problem_concept_candidates_linked_model_card_id_model_cards",
        "problem_concept_candidates",
        "model_cards",
        ["linked_model_card_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_problem_concept_candidates_linked_model_card_id_model_cards",
        "problem_concept_candidates",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_problem_concept_candidates_linked_model_card_id",
        table_name="problem_concept_candidates",
    )
    op.drop_column("problem_concept_candidates", "linked_model_card_id")
