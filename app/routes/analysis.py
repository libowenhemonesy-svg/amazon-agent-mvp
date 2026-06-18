"""分析工具路由"""
from __future__ import annotations

import os
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import build_llm_client
from app.analysis.ad_optimizer import AdOptimizer
from app.analysis.battlefield import BattlefieldAnalyzer
from app.analysis.diagnosis import DiagnosisAnalyzer
from app.analysis.fba_estimator import FbaEstimateInput, FbaEstimator
from app.analysis.listing_optimizer import ListingOptimizer
from app.analysis.product_research import ProductResearchAnalyzer
from app.analysis.profit_calculator import ProfitCalculationInput, ProfitCalculator
from app.analysis.supply_chain import SupplyChainAnalyzer
from app.db.models import AlertTask, ProfitCalculation, SalesDaily, SkuMaster
from app.deps import get_session, get_session_factory

router = APIRouter(prefix="/api", tags=["分析工具"])

battlefield_analyzer = BattlefieldAnalyzer()
diagnosis_analyzer = DiagnosisAnalyzer()
product_research_analyzer = ProductResearchAnalyzer()
listing_optimizer = ListingOptimizer()
supply_chain_analyzer = SupplyChainAnalyzer()
profit_calculator = ProfitCalculator()
fba_estimator = FbaEstimator()

# 由 main.py 初始化
_product_research_ai_enabled = True


def init_product_research_ai(enabled: bool) -> None:
    """初始化产品研究 AI 配置"""
    global _product_research_ai_enabled
    _product_research_ai_enabled = enabled


class ProductResearchRequest(BaseModel):
    keyword: str
    marketplace: str = "US"
    category: str = "all"


class ListingOptimizeRequest(BaseModel):
    product_description: str
    keywords: str | list[str] = ""
    marketplace: str = "US"
    competitor_asin: str = ""


class AdOptimizeRequest(BaseModel):
    product_keyword: str
    daily_budget: float
    target_acos: float
    marketplace: str = "US"
    category: str = "all"
    ad_type: str = "Sponsored Products"
    sku: str = ""
    days: int = 30


class AdAnalyzeRequest(BaseModel):
    sku: str
    days: int = 30


class SupplyChainAnalyzeRequest(BaseModel):
    product: str
    purchase_quantity: int
    marketplace: str = "US"
    logistics_method: str = "FBA sea freight"
    budget: float = 10000
    category: str = "all"


class ProfitCalculateRequest(BaseModel):
    product_name: str
    sku: str = ""
    marketplace: str = "US"
    sale_price: float
    landed_cost: float
    first_leg_freight: float = 0
    referral_rate: float = 0.15
    weight_oz: float = 12
    length_in: float = 8
    width_in: float = 6
    height_in: float = 3
    ad_acos: float = 0.15
    return_rate: float = 0.03
    monthly_units: int = 300
    monthly_fixed_cost: float = 300
    q4_peak: bool = False


class FbaEstimateRequest(BaseModel):
    weight_oz: float
    length_in: float
    width_in: float
    height_in: float
    category: str = "general"
    season: str = "normal"
    sale_price: float = 0
    landed_cost: float = 0
    monthly_units: int = 1


@router.get("/battlefield/analyze")
def analyze_battlefield(asin: str, marketplace: str = "US") -> dict:
    """分析竞品，生成战场地图"""
    return battlefield_analyzer.generate_demo_data(asin)


@router.get("/battlefield/data/{asin}")
def get_battlefield_data(asin: str) -> dict:
    """获取战场地图数据"""
    return {"asin": asin, "message": "请先运行分析"}


@router.get("/diagnosis/run")
def run_diagnosis(asin: str) -> dict:
    """运行产品诊断"""
    return diagnosis_analyzer.generate_demo_data(asin)


@router.get("/diagnosis/report/{asin}")
def get_diagnosis_report(asin: str) -> dict:
    """获取诊断报告"""
    return {"asin": asin, "message": "请先运行诊断"}


@router.post("/selection/research")
def run_product_research(
    payload: ProductResearchRequest,
    session: Session = Depends(get_session),
) -> dict:
    """基于 Chrome 采集商品池运行关键词选品研究。"""
    keyword = payload.keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")

    marketplace = (payload.marketplace or "US").upper()
    category = payload.category or "all"
    rows = session.scalars(select(SkuMaster).where(SkuMaster.store == "Amazon")).all()
    competitors = []
    for sku in rows:
        row_marketplace = (sku.marketplace or "US").upper()
        if row_marketplace != marketplace:
            continue
        if category != "all" and (sku.product_category or "").lower() != category.lower():
            continue
        competitors.append({
            "sku": sku.sku,
            "asin": sku.asin or sku.sku,
            "title": sku.title or sku.asin or sku.sku,
            "price": sku.price or 0,
            "rating": sku.rating or 0,
            "review_count": sku.review_count or 0,
            "main_image": sku.main_image or "",
            "url": sku.platform_link or "",
            "marketplace": row_marketplace,
            "category": sku.product_category or "",
        })

    return product_research_analyzer.analyze(
        keyword=keyword,
        marketplace=marketplace,
        category=category,
        competitors=competitors,
        llm_client=build_llm_client(os.environ) if _product_research_ai_enabled else None,
    )


@router.post("/listing/optimize")
def optimize_listing(payload: ListingOptimizeRequest) -> dict:
    """基于产品信息和关键词生成 Amazon Listing 内容与质量评分。"""
    product_description = payload.product_description.strip()
    if not product_description:
        raise HTTPException(status_code=400, detail="产品信息不能为空")

    try:
        return listing_optimizer.optimize(
            product_description=product_description,
            keywords=payload.keywords,
            marketplace=payload.marketplace,
            competitor_asin=payload.competitor_asin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ads/optimize")
def optimize_ads(payload: AdOptimizeRequest) -> dict:
    """基于预算、目标 ACoS 和关键词生成 Amazon 广告投放策略。

    如果提供 sku 参数，会从数据库读取真实广告数据进行分析，结果更精准。
    不提供 sku 时退化为基于规则的估算模式。
    """
    product_keyword = payload.product_keyword.strip()
    if not product_keyword:
        raise HTTPException(status_code=400, detail="产品关键词不能为空")

    try:
        optimizer = AdOptimizer(session_factory=get_session_factory())
        return optimizer.optimize(
            product_keyword=product_keyword,
            daily_budget=payload.daily_budget,
            target_acos=payload.target_acos,
            marketplace=payload.marketplace,
            category=payload.category,
            ad_type=payload.ad_type,
            sku=payload.sku or None,
            days=payload.days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ads/analyze")
def analyze_ads(payload: AdAnalyzeRequest) -> dict:
    """分析单个 SKU 的广告表现，输出诊断报告。

    基于真实广告数据，返回健康度评分、趋势分析、竞价调整建议、
    否定词挖掘和优化建议。
    """
    sku = payload.sku.strip()
    if not sku:
        raise HTTPException(status_code=400, detail="SKU 不能为空")

    try:
        optimizer = AdOptimizer(session_factory=get_session_factory())
        result = optimizer.analyze_sku_ads(sku=sku, days=payload.days)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"分析失败: {exc}") from exc


@router.post("/supply-chain/analyze")
def analyze_supply_chain(payload: SupplyChainAnalyzeRequest) -> dict:
    """基于采购参数生成供应链成本、物流、备货和风控方案。"""
    product = payload.product.strip()
    if not product:
        raise HTTPException(status_code=400, detail="产品不能为空")

    try:
        return supply_chain_analyzer.analyze(
            product=product,
            purchase_quantity=payload.purchase_quantity,
            marketplace=payload.marketplace,
            logistics_method=payload.logistics_method,
            budget=payload.budget,
            category=payload.category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/profit/calculate")
def calculate_profit(
    payload: ProfitCalculateRequest,
    session: Session = Depends(get_session),
) -> dict:
    """计算并保存 Amazon 单品利润核算快照。"""
    product_name = payload.product_name.strip()
    if not product_name:
        raise HTTPException(status_code=400, detail="产品名称不能为空")

    input_data = payload.model_dump()
    input_data["product_name"] = product_name
    input_data["sku"] = (payload.sku or "").strip()
    input_data["marketplace"] = (payload.marketplace or "US").upper()
    _validate_profit_input(input_data)

    calculation_input = ProfitCalculationInput(**input_data)
    result = profit_calculator.calculate(calculation_input)
    saved = ProfitCalculation(
        product_name=product_name,
        sku=input_data["sku"] or None,
        marketplace=input_data["marketplace"],
        input_data=input_data,
        result_data=result,
    )
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return _profit_calculation_dict(saved)


@router.get("/profit/calculations")
def list_profit_calculations(
    limit: int = 10,
    session: Session = Depends(get_session),
) -> dict:
    """列出最近保存的利润核算快照。"""
    bounded_limit = min(max(limit, 1), 50)
    rows = session.scalars(
        select(ProfitCalculation)
        .order_by(ProfitCalculation.created_at.desc(), ProfitCalculation.id.desc())
        .limit(bounded_limit)
    ).all()
    return {"items": [_profit_calculation_dict(row) for row in rows]}


@router.post("/fba/estimate")
def estimate_fba(payload: FbaEstimateRequest) -> dict:
    """估算 Amazon US FBA fulfillment、storage 和 referral 成本。"""
    input_data = payload.model_dump()
    _validate_fba_input(input_data)
    input_data["category"] = (payload.category or "general").lower()
    input_data["season"] = "peak" if payload.season == "peak" else "normal"
    return fba_estimator.estimate(FbaEstimateInput(**input_data))


def _validate_profit_input(input_data: dict) -> None:
    positive_fields = {
        "sale_price": "售价必须大于 0",
        "landed_cost": "进货成本必须大于 0",
        "monthly_units": "预期月销必须大于 0",
    }
    non_negative_fields = {
        "first_leg_freight": "头程运费不能小于 0",
        "monthly_fixed_cost": "月固定费不能小于 0",
        "weight_oz": "重量不能小于 0",
        "length_in": "长度不能小于 0",
        "width_in": "宽度不能小于 0",
        "height_in": "高度不能小于 0",
    }
    rate_fields = {
        "referral_rate": "佣金率必须在 0 到 1 之间",
        "ad_acos": "广告 ACoS 必须在 0 到 1 之间",
        "return_rate": "退货率必须在 0 到 1 之间",
    }
    for field, message in positive_fields.items():
        if input_data[field] <= 0:
            raise HTTPException(status_code=400, detail=message)
    for field, message in non_negative_fields.items():
        if input_data[field] < 0:
            raise HTTPException(status_code=400, detail=message)
    for field, message in rate_fields.items():
        if not 0 <= input_data[field] <= 1:
            raise HTTPException(status_code=400, detail=message)


def _validate_fba_input(input_data: dict) -> None:
    positive_fields = {
        "weight_oz": "重量必须大于 0",
        "length_in": "长度必须大于 0",
        "width_in": "宽度必须大于 0",
        "height_in": "高度必须大于 0",
        "monthly_units": "预计月销量必须大于 0",
    }
    non_negative_fields = {
        "sale_price": "售价不能小于 0",
        "landed_cost": "进货成本不能小于 0",
    }
    for field, message in positive_fields.items():
        if input_data[field] <= 0:
            raise HTTPException(status_code=400, detail=message)
    for field, message in non_negative_fields.items():
        if input_data[field] < 0:
            raise HTTPException(status_code=400, detail=message)


@router.get("/sales-monitor/overview")
def sales_monitor_overview(
    days: int = 30,
    end_date: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """销量监控概览：最近 N 天的告警和趋势。"""
    from sqlalchemy import func

    bounded_days = min(max(days, 7), 90)
    ref_date = _parse_date(end_date) or date.today()
    cutoff = ref_date - timedelta(days=bounded_days)

    # 查询销量相关告警
    sales_alert_types = ("sales_drop", "sales_declining_3d")
    alerts = session.scalars(
        select(AlertTask)
        .where(AlertTask.alert_type.in_(sales_alert_types))
        .where(AlertTask.date >= cutoff)
        .order_by(AlertTask.date.desc(), AlertTask.severity.desc())
        .limit(100)
    ).all()

    # 查询销量趋势（按日期聚合）
    trend_rows = session.execute(
        select(
            SalesDaily.date,
            func.sum(SalesDaily.units_sold).label("total_units"),
            func.sum(SalesDaily.sales_amount).label("total_sales"),
            func.count(func.distinct(SalesDaily.sku)).label("sku_count"),
        )
        .where(SalesDaily.date >= cutoff)
        .group_by(SalesDaily.date)
        .order_by(SalesDaily.date)
    ).all()

    # 汇总统计
    alert_count = len(alerts)
    affected_skus = len({a.sku for a in alerts})
    high_count = sum(1 for a in alerts if a.severity == "high")

    return {
        "alerts": [
            {
                "id": a.id,
                "date": a.date.isoformat(),
                "sku": a.sku,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "reason": a.reason,
                "rule_context": a.rule_context or {},
                "agent_result": a.agent_result or {},
                "status": a.status,
            }
            for a in alerts
        ],
        "trend": [
            {
                "date": row.date.isoformat(),
                "total_units": int(row.total_units or 0),
                "total_sales": round(float(row.total_sales or 0), 2),
                "sku_count": int(row.sku_count or 0),
            }
            for row in trend_rows
        ],
        "summary": {
            "alert_count": alert_count,
            "affected_skus": affected_skus,
            "high_count": high_count,
            "days": bounded_days,
        },
    }


@router.get("/sales-monitor/metrics/{sku}")
def sales_monitor_metrics(
    sku: str,
    days: int = 30,
    end_date: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """指定 SKU 的销量指标和告警历史。"""
    bounded_days = min(max(days, 7), 90)
    ref_date = _parse_date(end_date) or date.today()
    cutoff = ref_date - timedelta(days=bounded_days)

    # 销量数据
    sales = session.scalars(
        select(SalesDaily)
        .where(SalesDaily.sku == sku)
        .where(SalesDaily.date >= cutoff)
        .order_by(SalesDaily.date)
    ).all()

    # 告警历史
    sales_alert_types = ("sales_drop", "sales_declining_3d")
    alerts = session.scalars(
        select(AlertTask)
        .where(AlertTask.sku == sku)
        .where(AlertTask.alert_type.in_(sales_alert_types))
        .where(AlertTask.date >= cutoff)
        .order_by(AlertTask.date.desc())
    ).all()

    return {
        "sku": sku,
        "sales": [
            {
                "date": s.date.isoformat(),
                "units_sold": s.units_sold,
                "sales_amount": round(s.sales_amount, 2),
            }
            for s in sales
        ],
        "alerts": [
            {
                "id": a.id,
                "date": a.date.isoformat(),
                "alert_type": a.alert_type,
                "severity": a.severity,
                "reason": a.reason,
                "agent_result": a.agent_result or {},
                "status": a.status,
            }
            for a in alerts
        ],
    }


def _parse_date(value: str | None) -> date | None:
    """将 YYYY-MM-DD 字符串解析为 date，失败返回 None。"""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _profit_calculation_dict(row: ProfitCalculation) -> dict:
    return {
        "id": row.id,
        "product_name": row.product_name,
        "sku": row.sku or "",
        "marketplace": row.marketplace,
        "input": row.input_data or {},
        "result": row.result_data or {},
        "created_at": row.created_at.isoformat(),
    }
