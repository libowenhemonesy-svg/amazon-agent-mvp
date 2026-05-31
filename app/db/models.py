from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, UniqueConstraint
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
