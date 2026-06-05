from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_profit_calculations"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profit_calculations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=256), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=True),
        sa.Column("marketplace", sa.String(length=32), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("result_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_profit_calculations_product_name", "profit_calculations", ["product_name"])
    op.create_index("ix_profit_calculations_sku", "profit_calculations", ["sku"])
    op.create_index("ix_profit_calculations_marketplace", "profit_calculations", ["marketplace"])
    op.create_index("ix_profit_calculations_created_at", "profit_calculations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_profit_calculations_created_at", table_name="profit_calculations")
    op.drop_index("ix_profit_calculations_marketplace", table_name="profit_calculations")
    op.drop_index("ix_profit_calculations_sku", table_name="profit_calculations")
    op.drop_index("ix_profit_calculations_product_name", table_name="profit_calculations")
    op.drop_table("profit_calculations")
