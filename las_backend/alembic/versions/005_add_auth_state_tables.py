"""add auth state tables

Revision ID: 005
Revises: 004
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token", sa.String(length=2048), nullable=False),
        sa.Column("token_type", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(op.f("ix_revoked_tokens_token"), "revoked_tokens", ["token"], unique=False)

    op.create_table(
        "login_throttles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("client_ip", sa.String(length=100), nullable=True),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("blocked_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_key"),
    )
    op.create_index(op.f("ix_login_throttles_scope_key"), "login_throttles", ["scope_key"], unique=False)
    op.create_index(op.f("ix_login_throttles_username"), "login_throttles", ["username"], unique=False)
    op.create_index(op.f("ix_login_throttles_client_ip"), "login_throttles", ["client_ip"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_login_throttles_client_ip"), table_name="login_throttles")
    op.drop_index(op.f("ix_login_throttles_username"), table_name="login_throttles")
    op.drop_index(op.f("ix_login_throttles_scope_key"), table_name="login_throttles")
    op.drop_table("login_throttles")

    op.drop_index(op.f("ix_revoked_tokens_token"), table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
