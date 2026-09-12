"""add Chrome product captures

Revision ID: 0007_chrome_product_captures
Revises: 0006_image_creative_studio
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_chrome_product_captures"
down_revision = "0006_image_creative_studio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chrome_product_captures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asin", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("marketplace", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=False),
        sa.Column("bullets", sa.JSON(), nullable=False),
        sa.Column("reviews", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_chrome_product_captures_asin", "chrome_product_captures", ["asin"])
    op.create_index("ix_chrome_product_captures_marketplace", "chrome_product_captures", ["marketplace"])
    op.create_index("ix_chrome_product_captures_captured_at", "chrome_product_captures", ["captured_at"])


def downgrade() -> None:
    op.drop_table("chrome_product_captures")
