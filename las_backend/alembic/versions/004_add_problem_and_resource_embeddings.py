"""add problem and resource embeddings

Revision ID: 004
Revises: 003
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 64


def upgrade():
    op.add_column("problems", sa.Column("embedding", sa.JSON(), nullable=True))
    op.add_column("resource_links", sa.Column("embedding", sa.JSON(), nullable=True))

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        f"""
        ALTER TABLE problems
        ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSIONS})
        USING NULL::vector({EMBEDDING_DIMENSIONS})
        """
    )
    op.execute(
        f"""
        ALTER TABLE resource_links
        ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSIONS})
        USING NULL::vector({EMBEDDING_DIMENSIONS})
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_problems_embedding_ivfflat
        ON problems
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_resource_links_embedding_ivfflat
        ON resource_links
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_resource_links_embedding_ivfflat")
        op.execute("DROP INDEX IF EXISTS ix_problems_embedding_ivfflat")
        op.execute(
            """
            ALTER TABLE resource_links
            ALTER COLUMN embedding TYPE json
            USING NULL::json
            """
        )
        op.execute(
            """
            ALTER TABLE problems
            ALTER COLUMN embedding TYPE json
            USING NULL::json
            """
        )

    op.drop_column("resource_links", "embedding")
    op.drop_column("problems", "embedding")
