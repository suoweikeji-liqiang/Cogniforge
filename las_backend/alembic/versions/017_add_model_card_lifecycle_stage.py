"""add model card lifecycle stage

Revision ID: 017
Revises: 016
Create Date: 2026-03-10 17:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_cards") as batch_op:
        batch_op.add_column(
            sa.Column("lifecycle_stage", sa.String(length=20), nullable=False, server_default="active"),
        )
        batch_op.create_index("ix_model_cards_lifecycle_stage", ["lifecycle_stage"], unique=False)

    op.execute("UPDATE model_cards SET lifecycle_stage = 'active' WHERE lifecycle_stage IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("model_cards") as batch_op:
        batch_op.drop_index("ix_model_cards_lifecycle_stage")
        batch_op.drop_column("lifecycle_stage")
