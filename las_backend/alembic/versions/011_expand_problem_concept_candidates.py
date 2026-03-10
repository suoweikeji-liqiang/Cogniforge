"""expand problem concept candidates

Revision ID: 011_expand_problem_concept_candidates
Revises: 010
Create Date: 2026-03-08 13:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "011_expand_problem_concept_candidates"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "problem_concept_candidates",
        sa.Column("merged_into_concept", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("problem_concept_candidates", "merged_into_concept")
