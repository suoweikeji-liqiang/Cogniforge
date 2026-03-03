"""upgrade model card embeddings to pgvector

Revision ID: 003
Revises: 002
Create Date: 2026-03-03
"""

from alembic import op


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 64


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        f"""
        ALTER TABLE model_cards
        ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSIONS})
        USING NULL::vector({EMBEDDING_DIMENSIONS})
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_model_cards_embedding_ivfflat
        ON model_cards
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_model_cards_embedding_ivfflat")
    op.execute(
        """
        ALTER TABLE model_cards
        ALTER COLUMN embedding TYPE json
        USING NULL::json
        """
    )
