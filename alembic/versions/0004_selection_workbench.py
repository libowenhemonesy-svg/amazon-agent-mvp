from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_selection_workbench"
down_revision = "0003_memory_tables"
branch_labels = None
depends_on = None


def _indexes(table_name: str, *columns: str) -> None:
    for column in columns:
        op.create_index(f"ix_{table_name}_{column}", table_name, [column])


def upgrade() -> None:
    op.create_table(
        "selection_projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("marketplace", sa.String(length=32), nullable=False),
        sa.Column("target_currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_stage", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "selection_projects", "user_id", "marketplace", "status", "created_at", "updated_at"
    )

    op.create_table(
        "mcp_data_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("transport", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("capability_config_json", sa.JSON(), nullable=False),
        sa.Column("credential_reference", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    _indexes("mcp_data_sources", "enabled", "priority", "created_at", "updated_at")

    op.create_table(
        "freight_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("marketplace", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("pricing_mode", sa.String(length=32), nullable=False),
        sa.Column("minimum_billable_weight_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("first_weight_kg", sa.Numeric(18, 6), nullable=True),
        sa.Column("first_weight_fee", sa.Numeric(18, 6), nullable=True),
        sa.Column("additional_weight_unit_kg", sa.Numeric(18, 6), nullable=True),
        sa.Column("additional_weight_fee", sa.Numeric(18, 6), nullable=True),
        sa.Column("per_kg_rate", sa.Numeric(18, 6), nullable=True),
        sa.Column("volume_divisor", sa.Numeric(18, 6), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes("freight_templates", "marketplace", "effective_from", "enabled")

    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False),
        sa.Column("quote_currency", sa.String(length=8), nullable=False),
        sa.Column("rate", sa.Numeric(24, 10), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes("exchange_rates", "base_currency", "quote_currency", "collected_at")

    op.create_table(
        "keyword_research_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("input_type", sa.String(length=32), nullable=False),
        sa.Column("input_value", sa.String(length=512), nullable=False),
        sa.Column("marketplace", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=256), nullable=True),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_summary", sa.String(length=1024), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["selection_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes("keyword_research_runs", "project_id", "status", "started_at", "completed_at")

    op.create_table(
        "research_keywords",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("keyword", sa.String(length=512), nullable=False),
        sa.Column("normalized_keyword", sa.String(length=512), nullable=False),
        sa.Column("search_volume", sa.Float(), nullable=True),
        sa.Column("trend_rate", sa.Float(), nullable=True),
        sa.Column("trend_period", sa.String(length=64), nullable=True),
        sa.Column("product_count", sa.Integer(), nullable=True),
        sa.Column("competition_index", sa.Float(), nullable=True),
        sa.Column("cpc", sa.Float(), nullable=True),
        sa.Column("conversion_rate", sa.Float(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("opportunity_score", sa.Float(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("field_lineage_json", sa.JSON(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["selection_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["keyword_research_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "normalized_keyword", name="uq_research_keyword_run_word"
        ),
    )
    _indexes("research_keywords", "project_id", "run_id", "selected", "created_at")

    op.create_table(
        "product_directions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("keyword_cluster_json", sa.JSON(), nullable=False),
        sa.Column("market_metrics_json", sa.JSON(), nullable=False),
        sa.Column("competitors_json", sa.JSON(), nullable=False),
        sa.Column("field_lineage_json", sa.JSON(), nullable=False),
        sa.Column("data_completeness", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["selection_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes("product_directions", "project_id", "created_at", "updated_at")

    op.create_table(
        "pricing_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("product_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("domestic_shipping", sa.Numeric(18, 6), nullable=False),
        sa.Column("source_currency", sa.String(length=8), nullable=False),
        sa.Column("actual_weight_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("length_cm", sa.Numeric(18, 6), nullable=False),
        sa.Column("width_cm", sa.Numeric(18, 6), nullable=False),
        sa.Column("height_cm", sa.Numeric(18, 6), nullable=False),
        sa.Column("commission_rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("target_net_margin", sa.Numeric(18, 8), nullable=False),
        sa.Column("freight_template_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("exchange_rate_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("volumetric_weight_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("billable_weight_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("international_shipping", sa.Numeric(18, 6), nullable=False),
        sa.Column("target_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("commission_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("net_profit_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["selection_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes("pricing_snapshots", "project_id", "calculated_at")

    op.create_table(
        "selection_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("score_total", sa.Integer(), nullable=True),
        sa.Column("score_dimensions_json", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("risks_json", sa.JSON(), nullable=False),
        sa.Column("llm_status", sa.String(length=32), nullable=False),
        sa.Column("llm_report", sa.JSON(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["selection_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "selection_reports", "project_id", "decision", "llm_status", "generated_at"
    )

    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("research_run_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("request_json_redacted", sa.JSON(), nullable=False),
        sa.Column("response_json_redacted", sa.JSON(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["selection_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["research_run_id"], ["keyword_research_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "source_snapshots",
        "project_id",
        "research_run_id",
        "source_id",
        "capability",
        "collected_at",
    )


def downgrade() -> None:
    op.drop_table("source_snapshots")
    op.drop_table("selection_reports")
    op.drop_table("pricing_snapshots")
    op.drop_table("product_directions")
    op.drop_table("research_keywords")
    op.drop_table("keyword_research_runs")
    op.drop_table("exchange_rates")
    op.drop_table("freight_templates")
    op.drop_table("mcp_data_sources")
    op.drop_table("selection_projects")
