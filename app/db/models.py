from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SkuMaster(Base):
    __tablename__ = "sku_master"

    sku: Mapped[str] = mapped_column(String(128), primary_key=True)
    asin: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[float] = mapped_column(Float, default=0)
    rating: Mapped[float] = mapped_column(Float, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    main_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    platform_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    store: Mapped[str | None] = mapped_column(String(128), nullable=True)
    marketplace: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    responsible_agent: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(32), default="stable")
    target_acos: Mapped[float] = mapped_column(Float, default=0.3)
    target_gross_margin: Mapped[float] = mapped_column(Float, default=0.4)
    safety_stock_days: Mapped[int] = mapped_column(Integer, default=30)
    replenishment_days: Mapped[int] = mapped_column(Integer, default=20)
    enabled: Mapped[bool] = mapped_column(default=True)


class SalesDaily(Base):
    __tablename__ = "sales_daily"
    __table_args__ = (UniqueConstraint("sku", "date", name="uq_sales_daily_sku_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    units_sold: Mapped[int] = mapped_column(Integer, default=0)
    sales_amount: Mapped[float] = mapped_column(Float, default=0)


class AdsDaily(Base):
    __tablename__ = "ads_daily"
    __table_args__ = (UniqueConstraint("sku", "date", name="uq_ads_daily_sku_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    spend: Mapped[float] = mapped_column(Float, default=0)
    ad_orders: Mapped[int] = mapped_column(Integer, default=0)
    ad_sales: Mapped[float] = mapped_column(Float, default=0)


class InventoryDaily(Base):
    __tablename__ = "inventory_daily"
    __table_args__ = (UniqueConstraint("sku", "date", name="uq_inventory_daily_sku_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    available_inventory: Mapped[int] = mapped_column(Integer, default=0)
    inbound_inventory: Mapped[int] = mapped_column(Integer, default=0)
    reserved_inventory: Mapped[int] = mapped_column(Integer, default=0)


class ProfitDaily(Base):
    __tablename__ = "profit_daily"
    __table_args__ = (UniqueConstraint("sku", "date", name="uq_profit_daily_sku_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    product_cost: Mapped[float] = mapped_column(Float, default=0)
    platform_fees: Mapped[float] = mapped_column(Float, default=0)
    logistics_fees: Mapped[float] = mapped_column(Float, default=0)
    ad_spend: Mapped[float] = mapped_column(Float, default=0)


class ProfitCalculation(Base):
    __tablename__ = "profit_calculations"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_name: Mapped[str] = mapped_column(String(256), index=True)
    sku: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    marketplace: Mapped[str] = mapped_column(String(32), default="US", index=True)
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    result_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)


class ReturnReviewDaily(Base):
    __tablename__ = "return_review_daily"
    __table_args__ = (UniqueConstraint("sku", "date", name="uq_return_review_daily_sku_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    return_count: Mapped[int] = mapped_column(Integer, default=0)
    return_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    negative_reviews: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float] = mapped_column(Float, default=0)


class SkuMetricsDaily(Base):
    __tablename__ = "sku_metrics_daily"
    __table_args__ = (UniqueConstraint("sku", "date", name="uq_metrics_daily_sku_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    metrics: Mapped[dict] = mapped_column(JSON)


class AlertTask(Base):
    __tablename__ = "alert_tasks"
    __table_args__ = (UniqueConstraint("date", "sku", "alert_type", name="uq_alert_date_sku_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    alert_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    reason: Mapped[str] = mapped_column(String(512), default="")
    rule_context: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    agent_result: Mapped[dict] = mapped_column(JSON, default=dict)
    feishu_sync_status: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class DailyReport(Base):
    __tablename__ = "daily_reports"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_report_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    summary: Mapped[str] = mapped_column(String(2048))
    risk_count: Mapped[int] = mapped_column(Integer, default=0)
    pending_count: Mapped[int] = mapped_column(Integer, default=0)
    report_data: Mapped[dict] = mapped_column(JSON, default=dict)


class ConversationSession(Base):
    """聊天会话正本。"""
    __tablename__ = "conversation_sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), default="default", index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )


class ConversationMessage(Base):
    """聊天消息与工具调用摘要。"""
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    tool_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)


class MemoryItem(Base):
    """长期记忆正本；向量库只保存它的可检索副本。"""
    __tablename__ = "memory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), default="user", index=True)
    entity_type: Mapped[str] = mapped_column(String(64), default="user", index=True)
    entity_id: Mapped[str] = mapped_column(String(128), default="default", index=True)
    memory_type: Mapped[str] = mapped_column(String(64), default="preference", index=True)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64), default="user_explicit", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    vector_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )


# ==================== 战场地图 & 运营天眼 ====================


class CompetitorData(Base):
    """竞品数据表"""
    __tablename__ = "competitor_data"
    __table_args__ = (UniqueConstraint("target_asin", "competitor_asin", "date", name="uq_competitor_asin_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    target_asin: Mapped[str] = mapped_column(String(20), index=True)
    competitor_asin: Mapped[str] = mapped_column(String(20), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[float] = mapped_column(Float, default=0)
    rating: Mapped[float] = mapped_column(Float, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    bsr_rank: Mapped[int] = mapped_column(Integer, default=0)
    main_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    marketplace: Mapped[str] = mapped_column(String(10), default="US")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class CompetitorKeyword(Base):
    """竞品关键词表"""
    __tablename__ = "competitor_keywords"
    __table_args__ = (UniqueConstraint("target_asin", "keyword", "date", name="uq_keyword_asin_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    target_asin: Mapped[str] = mapped_column(String(20), index=True)
    competitor_asin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    keyword: Mapped[str] = mapped_column(String(200), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    search_volume: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[date] = mapped_column(Date, index=True)


class ReviewAnalysis(Base):
    """评论分析表"""
    __tablename__ = "review_analysis"
    __table_args__ = (UniqueConstraint("asin", "date", name="uq_review_analysis_asin_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    asin: Mapped[str] = mapped_column(String(20), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    positive_keywords: Mapped[dict] = mapped_column(JSON, default=list)
    negative_keywords: Mapped[dict] = mapped_column(JSON, default=list)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0)
    review_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class DiagnosisReport(Base):
    """诊断报告表"""
    __tablename__ = "diagnosis_reports"
    __table_args__ = (UniqueConstraint("asin", "date", name="uq_diagnosis_asin_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    asin: Mapped[str] = mapped_column(String(20), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    health_score: Mapped[float] = mapped_column(Float, default=0)
    traffic_health: Mapped[dict] = mapped_column(JSON, default=dict)
    conversion_efficiency: Mapped[dict] = mapped_column(JSON, default=dict)
    competitive_landscape: Mapped[dict] = mapped_column(JSON, default=dict)
    review_risk: Mapped[dict] = mapped_column(JSON, default=dict)
    recommendations: Mapped[dict] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(20), default="优化")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


# ==================== 用户认证 ====================


class User(Base):
    """企业用户 —— 管理员预设账号，不开放自主注册"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(16), default="user")  # admin / user
    is_active: Mapped[bool] = mapped_column(default=True)
    feishu_open_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 后续飞书扫码用
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ==================== AI 选品工作台 ====================


class SelectionProject(Base):
    __tablename__ = "selection_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    marketplace: Mapped[str] = mapped_column(String(32), index=True)
    target_currency: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    current_stage: Mapped[str] = mapped_column(String(32), default="keywords")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )


class McpDataSource(Base):
    __tablename__ = "mcp_data_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    url: Mapped[str] = mapped_column(String(1024))
    transport: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=10, index=True)
    capability_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    credential_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )


class KeywordResearchRun(Base):
    __tablename__ = "keyword_research_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("selection_projects.id", ondelete="CASCADE"), index=True
    )
    input_type: Mapped[str] = mapped_column(String(32))
    input_value: Mapped[str] = mapped_column(String(512))
    marketplace: Mapped[str] = mapped_column(String(32))
    category: Mapped[str | None] = mapped_column(String(256), nullable=True)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    error_summary: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class ResearchKeyword(Base):
    __tablename__ = "research_keywords"
    __table_args__ = (
        UniqueConstraint("run_id", "normalized_keyword", name="uq_research_keyword_run_word"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("selection_projects.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[int] = mapped_column(
        ForeignKey("keyword_research_runs.id", ondelete="CASCADE"), index=True
    )
    keyword: Mapped[str] = mapped_column(String(512))
    normalized_keyword: Mapped[str] = mapped_column(String(512))
    search_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend_period: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    competition_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpc: Mapped[float | None] = mapped_column(Float, nullable=True)
    conversion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    field_lineage_json: Mapped[dict] = mapped_column(JSON, default=dict)
    selected: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)


class ProductDirection(Base):
    __tablename__ = "product_directions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("selection_projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(256))
    keyword_cluster_json: Mapped[dict] = mapped_column(JSON, default=dict)
    market_metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    competitors_json: Mapped[dict] = mapped_column(JSON, default=dict)
    field_lineage_json: Mapped[dict] = mapped_column(JSON, default=dict)
    data_completeness: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )


class FreightTemplate(Base):
    __tablename__ = "freight_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    marketplace: Mapped[str] = mapped_column(String(32), index=True)
    country: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(8))
    pricing_mode: Mapped[str] = mapped_column(String(32))
    minimum_billable_weight_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    first_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    first_weight_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    additional_weight_unit_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    additional_weight_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    per_kg_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volume_divisor: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=6000)
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    enabled: Mapped[bool] = mapped_column(default=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(8), index=True)
    quote_currency: Mapped[str] = mapped_column(String(8), index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(24, 10))
    source_name: Mapped[str] = mapped_column(String(128))
    source_type: Mapped[str] = mapped_column(String(32))
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)


class PricingSnapshot(Base):
    __tablename__ = "pricing_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("selection_projects.id", ondelete="CASCADE"), index=True
    )
    product_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    domestic_shipping: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    source_currency: Mapped[str] = mapped_column(String(8))
    actual_weight_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    length_cm: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    width_cm: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    height_cm: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    target_net_margin: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    freight_template_snapshot_json: Mapped[dict] = mapped_column(JSON)
    exchange_rate_snapshot_json: Mapped[dict] = mapped_column(JSON)
    volumetric_weight_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    billable_weight_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    international_shipping: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    target_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    net_profit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)


class SelectionReport(Base):
    __tablename__ = "selection_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("selection_projects.id", ondelete="CASCADE"), index=True
    )
    score_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_dimensions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    risks_json: Mapped[dict] = mapped_column(JSON, default=dict)
    llm_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    llm_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("selection_projects.id", ondelete="CASCADE"), index=True
    )
    research_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("keyword_research_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    capability: Mapped[str] = mapped_column(String(64), index=True)
    tool_name: Mapped[str] = mapped_column(String(128))
    request_json_redacted: Mapped[dict] = mapped_column(JSON, default=dict)
    response_json_redacted: Mapped[dict] = mapped_column(JSON, default=dict)
    truncated: Mapped[bool] = mapped_column(default=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)


# ==================== 图片创意工作台 ====================


class ImageBoard(Base):
    __tablename__ = "image_boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), index=True
    )


class ImagePrompt(Base):
    """运营团队沉淀并复用的图片提示词。"""

    __tablename__ = "image_prompts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    category: Mapped[str] = mapped_column(String(64), default="custom", index=True)
    content: Mapped[str] = mapped_column(Text)
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), index=True
    )


class ImageWorkflow(Base):
    __tablename__ = "image_workflows"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )


class ImageWorkflowVersion(Base):
    __tablename__ = "image_workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_image_workflow_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("image_workflows.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    graph_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)


class ImageWorkflowRun(Base):
    __tablename__ = "image_workflow_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("image_workflows.id", ondelete="CASCADE"), index=True
    )
    workflow_version: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    node_log_json: Mapped[list] = mapped_column(JSON, default=list)
    error_summary: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class ImageAsset(Base):
    __tablename__ = "image_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("image_workflow_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
   
    kind: Mapped[str] = mapped_column(String(32), default="generated", index=True)
    filename: Mapped[str] = mapped_column(String(256))
    url: Mapped[str] = mapped_column(String(1024))
    mime_type: Mapped[str] = mapped_column(String(64), default="image/png")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
