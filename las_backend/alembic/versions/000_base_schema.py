"""create base application schema

Revision ID: 000
Revises:
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa


revision = "000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("smtp_host", sa.String(length=200), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False),
        sa.Column("smtp_user", sa.String(length=200), nullable=False),
        sa.Column("smtp_password", sa.String(length=200), nullable=False),
        sa.Column("from_email", sa.String(length=200), nullable=False),
        sa.Column("from_name", sa.String(length=100), nullable=True),
        sa.Column("use_tls", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
    )
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("api_key", sa.String(length=500), nullable=True),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("role", sa.String(length=20), nullable=True, server_default=sa.text("'user'")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "llm_models",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("llm_providers.id"), nullable=False),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "problems",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("associated_concepts", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True, server_default=sa.text("'new'")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "model_cards",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("concept_maps", sa.JSON(), nullable=True),
        sa.Column("user_notes", sa.Text(), nullable=True),
        sa.Column("examples", sa.JSON(), nullable=True),
        sa.Column("counter_examples", sa.JSON(), nullable=True),
        sa.Column("migration_attempts", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True, server_default=sa.text("1")),
        sa.Column("parent_id", sa.String(length=36), sa.ForeignKey("model_cards.id"), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(length=100), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_password_reset_tokens_token", "password_reset_tokens", ["token"], unique=True)

    op.create_table(
        "practice_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("model_card_id", sa.String(length=36), sa.ForeignKey("model_cards.id"), nullable=True),
        sa.Column("task_type", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("review_type", sa.String(length=50), nullable=True),
        sa.Column("period", sa.String(length=50), nullable=True),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "quick_notes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=True, server_default=sa.text("'text'")),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "resource_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("link_type", sa.String(length=20), nullable=True, server_default=sa.text("'webpage'")),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True, server_default=sa.text("'unread'")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("problem_id", sa.String(length=36), sa.ForeignKey("problems.id"), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("messages", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "cognitive_challenges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_card_id", sa.String(length=36), sa.ForeignKey("model_cards.id"), nullable=True),
        sa.Column("challenge_type", sa.String(length=50), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("user_answer", sa.Text(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "evolution_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("model_id", sa.String(length=36), sa.ForeignKey("model_cards.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action_taken", sa.String(length=50), nullable=True),
        sa.Column("previous_version_id", sa.String(length=36), sa.ForeignKey("model_cards.id"), nullable=True),
        sa.Column("reason_for_change", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "learning_paths",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("problem_id", sa.String(length=36), sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("path_data", sa.JSON(), nullable=True),
        sa.Column("current_step", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("problem_id"),
    )
    op.create_table(
        "practice_submissions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("practice_task_id", sa.String(length=36), sa.ForeignKey("practice_tasks.id"), nullable=False),
        sa.Column("solution", sa.Text(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "problem_responses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("problem_id", sa.String(length=36), sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("user_response", sa.Text(), nullable=False),
        sa.Column("system_feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "review_schedules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_card_id", sa.String(length=36), sa.ForeignKey("model_cards.id"), nullable=False),
        sa.Column("ease_factor", sa.Integer(), nullable=True, server_default=sa.text("2500")),
        sa.Column("interval_days", sa.Integer(), nullable=True, server_default=sa.text("1")),
        sa.Column("repetitions", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("next_review_at", sa.DateTime(), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("conversation_messages")
    op.drop_table("review_schedules")
    op.drop_table("problem_responses")
    op.drop_table("practice_submissions")
    op.drop_table("learning_paths")
    op.drop_table("evolution_logs")
    op.drop_table("cognitive_challenges")
    op.drop_table("conversations")
    op.drop_table("resource_links")
    op.drop_table("quick_notes")
    op.drop_table("reviews")
    op.drop_table("practice_tasks")
    op.drop_index("ix_password_reset_tokens_token", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_table("model_cards")
    op.drop_table("problems")
    op.drop_table("llm_models")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_system_settings_key", table_name="system_settings")
    op.drop_table("users")
    op.drop_table("system_settings")
    op.drop_table("llm_providers")
    op.drop_table("email_config")
