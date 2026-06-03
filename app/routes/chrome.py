"""Chrome 插件数据接收路由"""
from __future__ import annotations

import json
import os
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import build_llm_client
from app.db.models import SkuMaster
from app.deps import get_session, get_session_factory

router = APIRouter(prefix="/api/chrome", tags=["Chrome 插件"])

# Chrome 插件 API Key（从环境变量读取）
CHROME_API_KEY = os.getenv("CHROME_API_KEY", "")


def _parse_price(raw: object) -> float:
    """Parse Amazon price text from US/CN localized formats."""
    text = str(raw or "")
    match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)", text)
    if not match:
        return 0
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return 0


def _parse_rating(raw: object) -> float:
    text = str(raw or "")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return 0
    try:
        return float(match.group(1))
    except ValueError:
        return 0


def _parse_review_count(raw: object) -> int:
    text = str(raw or "")
    match = re.search(r"(\d+(?:,\d{3})*)", text)
    if not match:
        return 0
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return 0


def _verify_api_key(request: Request):
    """验证 Chrome 插件 API Key"""
    if not CHROME_API_KEY:
        return  # 未配置则跳过验证
    api_key = request.headers.get("X-API-Key", "")
    if api_key != CHROME_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")


@router.post("/submit")
async def submit_chrome_data(request: Request) -> dict:
    """接收 Chrome 插件提取的商品数据"""
    _verify_api_key(request)

    try:
        body = await request.json()
        title = body.get("title", "")
        price_raw = body.get("price", "")
        rating_raw = body.get("rating", "")
        review_count_raw = body.get("review_count", "")
        bullets = body.get("bullets", [])
        image = body.get("image", "")
        url = body.get("url", "")
        asin = body.get("asin", "")
        reviews = body.get("reviews", [])

        price = _parse_price(price_raw)
        rating = _parse_rating(rating_raw)
        review_count = _parse_review_count(review_count_raw)

        # 保存到数据库
        session_factory = get_session_factory()
        with session_factory() as session:
            if asin:
                existing = session.scalar(
                    select(SkuMaster).where(SkuMaster.asin == asin)
                )

                if existing:
                    existing.title = title or existing.title
                    existing.price = price if price else existing.price
                    existing.rating = rating if rating else existing.rating
                    existing.review_count = review_count if review_count else existing.review_count
                    existing.main_image = image or existing.main_image
                    existing.platform_link = url or existing.platform_link
                else:
                    new_sku = SkuMaster(
                        sku=asin,
                        asin=asin,
                        title=title,
                        price=price,
                        rating=rating,
                        review_count=review_count,
                        main_image=image,
                        platform_link=url,
                        store="Amazon",
                        marketplace="US",
                        product_category="",
                        lifecycle="new",
                    )
                    session.add(new_sku)

                session.commit()

        return {
            "success": True,
            "message": "数据已保存",
            "asin": asin,
            "price": price,
            "rating": rating,
            "review_count": review_count,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/products")
def get_chrome_products() -> dict:
    """获取通过 Chrome 插件提交的商品列表"""
    session_factory = get_session_factory()
    with session_factory() as session:
        skus = session.scalars(
            select(SkuMaster).where(SkuMaster.store == "Amazon").limit(50)
        ).all()

        products = []
        for sku in skus:
            products.append({
                "asin": sku.asin or sku.sku,
                "title": sku.title or sku.asin or sku.sku,
                "price": sku.price or 0,
                "rating": sku.rating or 0,
                "review_count": sku.review_count or 0,
                "main_image": sku.main_image or "",
                "url": sku.platform_link or "",
                "marketplace": sku.marketplace or "US",
            })

        return {"products": products}


@router.delete("/products/{asin}")
def delete_chrome_product(asin: str) -> dict:
    """删除 Chrome 插件采集的商品"""
    try:
        session_factory = get_session_factory()
        with session_factory() as session:
            sku = session.scalar(
                select(SkuMaster).where(SkuMaster.asin == asin)
            )
            if not sku:
                return {"success": False, "error": "商品不存在"}

            session.delete(sku)
            session.commit()
            return {"success": True, "message": f"已删除 {asin}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/products/delete-batch")
async def delete_batch_products(request: Request) -> dict:
    """批量删除商品"""
    try:
        body = await request.json()
        asins = body.get("asins", [])
        if not asins:
            return {"success": False, "error": "未选择商品"}

        deleted = 0
        session_factory = get_session_factory()
        with session_factory() as session:
            for asin in asins:
                sku = session.scalar(
                    select(SkuMaster).where(SkuMaster.asin == asin)
                )
                if sku:
                    session.delete(sku)
                    deleted += 1
            session.commit()

        return {"success": True, "message": f"已删除 {deleted} 个商品", "deleted": deleted}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/analyze")
async def analyze_products(request: Request) -> dict:
    """AI 分析选中的商品"""
    try:
        body = await request.json()
        asins = body.get("asins", [])

        # 获取商品数据
        products = []
        session_factory = get_session_factory()
        with session_factory() as session:
            for asin in asins:
                sku = session.scalar(
                    select(SkuMaster).where(SkuMaster.asin == asin)
                )
                if sku:
                    products.append({
                        "asin": sku.asin,
                        "title": sku.title or "",
                        "price": sku.price or 0,
                        "rating": sku.rating or 0,
                        "review_count": sku.review_count or 0,
                    })

        if not products:
            return {"success": False, "error": "未找到商品数据"}

        # 构建分析提示词
        product_info = "\n".join([
            f"- ASIN: {p['asin']}, 标题: {p['title']}, 价格: ${p['price']}, 评分: {p['rating']}★, 评论数: {p['review_count']}"
            for p in products
        ])

        prompt = f"""你是一位资深亚马逊选品专家。请分析以下商品数据，给出专业的选品建议。

商品数据：
{product_info}

请从以下维度分析并给出结论：
1. 市场潜力（价格区间、需求量）
2. 竞争程度（评分分布、评论数量）
3. 利润空间（定价建议）
4. 风险提示（退货率、差评关键词）
5. 综合推荐指数（0-100分）

请用简洁的中文回答，使用 JSON 格式返回：
{{
  "score": 推荐指数,
  "summary": "一句话总结",
  "market_potential": "市场潜力分析",
  "competition": "竞争程度分析",
  "profit_advice": "利润建议",
  "risks": ["风险1", "风险2"],
  "suggestions": ["建议1", "建议2"]
}}"""

        # 调用 AI 分析（复用 LLMClient 抽象）
        llm_client = build_llm_client(os.environ)
        system_prompt = "你是亚马逊选品分析专家，返回 JSON 格式的分析结果。"
        ai_text = llm_client.generate(system_prompt, prompt)

        # 解析 JSON
        # 提取 JSON 部分
        if "```json" in ai_text:
            ai_text = ai_text.split("```json")[1].split("```")[0].strip()
        elif "```" in ai_text:
            ai_text = ai_text.split("```")[1].split("```")[0].strip()

        try:
            result = json.loads(ai_text)
        except json.JSONDecodeError:
            result = {
                "score": 70,
                "summary": ai_text[:200],
                "market_potential": "需要更多数据",
                "competition": "中等",
                "profit_advice": "建议优化定价",
                "risks": ["数据不足"],
                "suggestions": ["补充更多商品信息"]
            }

        return {"success": True, "analysis": result, "product_count": len(products)}

    except Exception as e:
        return {"success": False, "error": str(e)}
