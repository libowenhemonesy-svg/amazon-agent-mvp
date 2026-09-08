"""add image creative boards and prompt library

Revision ID: 0006_image_creative_studio
Revises: 0005_image_workflows
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_image_creative_studio"
down_revision = "0005_image_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_boards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_image_boards_user_id", "image_boards", ["user_id"])
    op.create_index("ix_image_boards_sku", "image_boards", ["sku"])
    op.create_index("ix_image_boards_status", "image_boards", ["status"])
    op.create_index("ix_image_boards_created_at", "image_boards", ["created_at"])
    op.create_index("ix_image_boards_updated_at", "image_boards", ["updated_at"])
    op.create_table(
        "image_prompts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_image_prompts_user_id", "image_prompts", ["user_id"])
    op.create_index("ix_image_prompts_category", "image_prompts", ["category"])
    op.create_index("ix_image_prompts_created_at", "image_prompts", ["created_at"])
    op.create_index("ix_image_prompts_updated_at", "image_prompts", ["updated_at"])


def downgrade() -> None:
    op.drop_table("image_prompts")
    op.drop_table("image_boards")
