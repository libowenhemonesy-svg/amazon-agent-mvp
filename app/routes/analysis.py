"""分析工具路由"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import build_llm_client
from app.analysis.ad_optimizer import AdOptimizer
from app.analysis.battlefield import BattlefieldAnalyzer
from app.analysis.diagnosis import DiagnosisAnalyzer
from app.analysis.listing_optimizer import ListingOptimizer
from app.analysis.product_research import ProductResearchAnalyzer
from app.analysis.supply_chain import SupplyChainAnalyzer
from app.db.models import SkuMaster
from app.deps import get_session

router = APIRouter(prefix="/api", tags=["分析工具"])

battlefield_analyzer = BattlefieldAnalyzer()
diagnosis_analyzer = DiagnosisAnalyzer()
product_research_analyzer = ProductResearchAnalyzer()
listing_optimizer = ListingOptimizer()
ad_optimizer = AdOptimizer()
supply_chain_analyzer = SupplyChainAnalyzer()

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


class SupplyChainAnalyzeRequest(BaseModel):
    product: str
    purchase_quantity: int
    marketplace: str = "US"
    logistics_method: str = "FBA sea freight"
    budget: float = 10000
    category: str = "all"


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
    """基于预算、目标 ACoS 和关键词生成 Amazon 广告投放策略。"""
    product_keyword = payload.product_keyword.strip()
    if not product_keyword:
        raise HTTPException(status_code=400, detail="产品关键词不能为空")

    try:
        return ad_optimizer.optimize(
            product_keyword=product_keyword,
            daily_budget=payload.daily_budget,
            target_acos=payload.target_acos,
            marketplace=payload.marketplace,
            category=payload.category,
            ad_type=payload.ad_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
