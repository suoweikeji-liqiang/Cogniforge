"""add retrieval events

Revision ID: 006
Revises: 005
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "retrieval_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("retrieval_context", sa.Text(), nullable=True),
        sa.Column("items", sa.JSON(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_retrieval_events_user_id"), "retrieval_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_retrieval_events_source"), "retrieval_events", ["source"], unique=False)
    op.create_index(op.f("ix_retrieval_events_created_at"), "retrieval_events", ["created_at"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_retrieval_events_created_at"), table_name="retrieval_events")
    op.drop_index(op.f("ix_retrieval_events_source"), table_name="retrieval_events")
    op.drop_index(op.f("ix_retrieval_events_user_id"), table_name="retrieval_events")
    op.drop_table("retrieval_events")
