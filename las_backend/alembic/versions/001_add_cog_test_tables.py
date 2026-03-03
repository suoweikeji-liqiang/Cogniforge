"""add cog test tables

Revision ID: 001
Revises:
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = "000"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cog_test_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("concept", sa.String(), nullable=False),
        sa.Column("model_card_id", sa.String(36), sa.ForeignKey("model_cards.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=True, server_default=sa.text("'active'")),
        sa.Column("agent_mode", sa.String(20), nullable=True, server_default=sa.text("'guide_challenger'")),
        sa.Column("max_rounds", sa.Integer(), nullable=True, server_default=sa.text("3")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "cog_test_turns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("cog_test_sessions.id"), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("dialogue_text", sa.Text(), nullable=False),
        sa.Column("analysis_json", sa.Text(), nullable=True),
        sa.Column("understanding_level", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "cog_test_blind_spots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("cog_test_sessions.id"), nullable=False),
        sa.Column("turn_id", sa.String(36), sa.ForeignKey("cog_test_turns.id"), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "cog_test_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("cog_test_sessions.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=True),
        sa.Column("understanding_score", sa.String(10), nullable=True),
        sa.Column("blind_spot_count", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("snapshot_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("cog_test_snapshots")
    op.drop_table("cog_test_blind_spots")
    op.drop_table("cog_test_turns")
    op.drop_table("cog_test_sessions")
