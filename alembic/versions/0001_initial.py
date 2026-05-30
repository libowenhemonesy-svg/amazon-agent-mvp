from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sku_master",
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("asin", sa.String(length=128), nullable=True),
        sa.Column("platform_link", sa.String(length=512), nullable=True),
        sa.Column("store", sa.String(length=128), nullable=True),
        sa.Column("marketplace", sa.String(length=32), nullable=True),
        sa.Column("product_category", sa.String(length=128), nullable=True),
        sa.Column("owner", sa.String(length=128), nullable=True),
        sa.Column("responsible_agent", sa.String(length=128), nullable=True),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("target_acos", sa.Float(), nullable=False),
        sa.Column("target_gross_margin", sa.Float(), nullable=False),
        sa.Column("safety_stock_days", sa.Integer(), nullable=False),
        sa.Column("replenishment_days", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("sku"),
    )
    op.create_table(
        "sales_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("units_sold", sa.Integer(), nullable=False),
        sa.Column("sales_amount", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", "date", name="uq_sales_daily_sku_date"),
    )
    op.create_index("ix_sales_daily_sku", "sales_daily", ["sku"])
    op.create_index("ix_sales_daily_date", "sales_daily", ["date"])
    op.create_table(
        "ads_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("spend", sa.Float(), nullable=False),
        sa.Column("ad_orders", sa.Integer(), nullable=False),
        sa.Column("ad_sales", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", "date", name="uq_ads_daily_sku_date"),
    )
    op.create_index("ix_ads_daily_sku", "ads_daily", ["sku"])
    op.create_index("ix_ads_daily_date", "ads_daily", ["date"])
    op.create_table(
        "inventory_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("available_inventory", sa.Integer(), nullable=False),
        sa.Column("inbound_inventory", sa.Integer(), nullable=False),
        sa.Column("reserved_inventory", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", "date", name="uq_inventory_daily_sku_date"),
    )
    op.create_index("ix_inventory_daily_sku", "inventory_daily", ["sku"])
    op.create_index("ix_inventory_daily_date", "inventory_daily", ["date"])
    op.create_table(
        "profit_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("product_cost", sa.Float(), nullable=False),
        sa.Column("platform_fees", sa.Float(), nullable=False),
        sa.Column("logistics_fees", sa.Float(), nullable=False),
        sa.Column("ad_spend", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", "date", name="uq_profit_daily_sku_date"),
    )
    op.create_index("ix_profit_daily_sku", "profit_daily", ["sku"])
    op.create_index("ix_profit_daily_date", "profit_daily", ["date"])
    op.create_table(
        "return_review_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("return_count", sa.Integer(), nullable=False),
        sa.Column("return_reason", sa.String(length=256), nullable=True),
        sa.Column("negative_reviews", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", "date", name="uq_return_review_daily_sku_date"),
    )
    op.create_index("ix_return_review_daily_sku", "return_review_daily", ["sku"])
    op.create_index("ix_return_review_daily_date", "return_review_daily", ["date"])
    op.create_table(
        "sku_metrics_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", "date", name="uq_metrics_daily_sku_date"),
    )
    op.create_index("ix_sku_metrics_daily_sku", "sku_metrics_daily", ["sku"])
    op.create_index("ix_sku_metrics_daily_date", "sku_metrics_daily", ["date"])
    op.create_table(
        "alert_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column("rule_context", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("agent_result", sa.JSON(), nullable=False),
        sa.Column("feishu_sync_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "sku", "alert_type", name="uq_alert_date_sku_type"),
    )
    op.create_index("ix_alert_tasks_date", "alert_tasks", ["date"])
    op.create_index("ix_alert_tasks_sku", "alert_tasks", ["sku"])
    op.create_index("ix_alert_tasks_alert_type", "alert_tasks", ["alert_type"])
    op.create_table(
        "daily_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("summary", sa.String(length=2048), nullable=False),
        sa.Column("risk_count", sa.Integer(), nullable=False),
        sa.Column("pending_count", sa.Integer(), nullable=False),
        sa.Column("report_data", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", name="uq_daily_report_date"),
    )
    op.create_index("ix_daily_reports_date", "daily_reports", ["date"])


def downgrade() -> None:
    op.drop_index("ix_daily_reports_date", table_name="daily_reports")
    op.drop_table("daily_reports")
    op.drop_index("ix_alert_tasks_alert_type", table_name="alert_tasks")
    op.drop_index("ix_alert_tasks_sku", table_name="alert_tasks")
    op.drop_index("ix_alert_tasks_date", table_name="alert_tasks")
    op.drop_table("alert_tasks")
    op.drop_index("ix_sku_metrics_daily_date", table_name="sku_metrics_daily")
    op.drop_index("ix_sku_metrics_daily_sku", table_name="sku_metrics_daily")
    op.drop_table("sku_metrics_daily")
    op.drop_index("ix_return_review_daily_date", table_name="return_review_daily")
    op.drop_index("ix_return_review_daily_sku", table_name="return_review_daily")
    op.drop_table("return_review_daily")
    op.drop_index("ix_profit_daily_date", table_name="profit_daily")
    op.drop_index("ix_profit_daily_sku", table_name="profit_daily")
    op.drop_table("profit_daily")
    op.drop_index("ix_inventory_daily_date", table_name="inventory_daily")
    op.drop_index("ix_inventory_daily_sku", table_name="inventory_daily")
    op.drop_table("inventory_daily")
    op.drop_index("ix_ads_daily_date", table_name="ads_daily")
    op.drop_index("ix_ads_daily_sku", table_name="ads_daily")
    op.drop_table("ads_daily")
    op.drop_index("ix_sales_daily_date", table_name="sales_daily")
    op.drop_index("ix_sales_daily_sku", table_name="sales_daily")
    op.drop_table("sales_daily")
    op.drop_table("sku_master")
