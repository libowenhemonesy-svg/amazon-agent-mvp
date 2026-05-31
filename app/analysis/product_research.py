"""AI 选品研究分析模块。"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from statistics import mean
from typing import Any

from app.agents.llm import DeepSeekLLMClient, LLMClient


@dataclass(frozen=True)
class _ScoredCompetitor:
    data: dict[str, Any]
    relevance: int


class ProductResearchAnalyzer:
    """基于 Chrome 采集商品池生成关键词选品研究结果。"""

    _INTENT_MODIFIERS = [
        "rechargeable",
        "portable",
        "mini",
        "for travel",
        "quiet",
        "usb",
        "battery operated",
        "handheld",
        "small",
        "for office",
        "for camping",
        "with clip",
    ]

    def analyze(
        self,
        *,
        keyword: str,
        marketplace: str,
        category: str = "all",
        competitors: list[dict[str, Any]] | None = None,
        llm_client: LLMClient | None = None,
    ) -> dict[str, Any]:
        normalized_keyword = self._normalize_keyword(keyword)
        if not normalized_keyword:
            raise ValueError("关键词不能为空")

        all_competitors = competitors or []
        selected, matched_count = self._select_competitors(normalized_keyword, all_competitors)
        market_overview = self._build_market_overview(selected, matched_count, len(all_competitors))
        keywords = self._build_blue_ocean_keywords(normalized_keyword, market_overview)
        competitor_cards = self._build_competitor_cards(selected)
        pricing_advice = self._build_pricing_advice(market_overview)
        decision = self._build_decision(market_overview, pricing_advice)
        rule_report = self._build_rule_report(
            keyword=normalized_keyword,
            marketplace=marketplace.upper(),
            market_overview=market_overview,
            keywords=keywords,
            pricing_advice=pricing_advice,
            decision=decision,
        )

        report = rule_report
        generated_by_ai = False
        if isinstance(llm_client, DeepSeekLLMClient):
            try:
                report = self._polish_report_with_ai(
                    llm_client=llm_client,
                    rule_report=rule_report,
                    keyword=normalized_keyword,
                    market_overview=market_overview,
                    keywords=keywords,
                    pricing_advice=pricing_advice,
                    decision=decision,
                )
                generated_by_ai = True
            except Exception:
                report = rule_report

        return {
            "keyword": normalized_keyword,
            "marketplace": marketplace.upper(),
            "category": category or "all",
            "market_overview": market_overview,
            "keywords": keywords,
            "competitors": competitor_cards,
            "pricing_advice": pricing_advice,
            "decision": decision,
            "report": report,
            "generated_by_ai": generated_by_ai,
        }

    def _select_competitors(
        self,
        keyword: str,
        competitors: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int]:
        tokens = [token for token in keyword.split() if token]
        scored: list[_ScoredCompetitor] = []
        for competitor in competitors:
            haystack = f"{competitor.get('title', '')} {competitor.get('asin', '')}".lower()
            relevance = sum(1 for token in tokens if token in haystack)
            if keyword in haystack:
                relevance += 3
            if relevance > 0:
                scored.append(_ScoredCompetitor(competitor, relevance))

        if scored:
            scored.sort(
                key=lambda item: (
                    item.relevance,
                    self._to_int(item.data.get("review_count")),
                    self._to_float(item.data.get("rating")),
                ),
                reverse=True,
            )
            return [item.data for item in scored[:10]], len(scored)

        fallback = sorted(
            competitors,
            key=lambda item: (
                self._to_int(item.get("review_count")),
                self._to_float(item.get("rating")),
            ),
            reverse=True,
        )
        return fallback[:10], 0

    def _build_market_overview(
        self,
        competitors: list[dict[str, Any]],
        matched_count: int,
        total_count: int,
    ) -> dict[str, Any]:
        prices = [self._to_float(item.get("price")) for item in competitors if self._to_float(item.get("price")) > 0]
        reviews = [self._to_int(item.get("review_count")) for item in competitors]
        ratings = [self._to_float(item.get("rating")) for item in competitors if self._to_float(item.get("rating")) > 0]

        avg_price = round(mean(prices), 2) if prices else 0
        avg_reviews = round(mean(reviews)) if reviews else 0
        avg_rating = round(mean(ratings), 1) if ratings else 0
        monthly_sales = self._estimate_monthly_sales(competitors)
        competition_score = self._competition_score(
            sample_size=len(competitors),
            avg_reviews=avg_reviews,
            avg_rating=avg_rating,
            prices=prices,
        )
        competition_level = self._competition_level(competition_score)
        opportunity_score = self._opportunity_score(
            monthly_sales=monthly_sales,
            competition_score=competition_score,
            avg_price=avg_price,
        )
        sample_limited = matched_count < 3
        sample_note = ""
        if matched_count == 0:
            sample_note = "未找到标题或 ASIN 直接匹配关键词的采集商品，已使用当前站点采集商品作为参考池。"
        elif matched_count < 3:
            sample_note = "关键词直接匹配样本少于 3 个，建议继续用 Chrome 插件采集更多竞品后复核。"

        return {
            "monthly_sales_estimate": monthly_sales,
            "avg_price": avg_price,
            "competition": competition_level,
            "competition_score": competition_score,
            "opportunity_score": opportunity_score,
            "sample_size": len(competitors),
            "matched_count": matched_count,
            "total_competitor_pool": total_count,
            "avg_reviews": avg_reviews,
            "avg_rating": avg_rating,
            "sample_limited": sample_limited,
            "sample_note": sample_note,
        }

    def _build_blue_ocean_keywords(
        self,
        keyword: str,
        market_overview: dict[str, Any],
    ) -> list[dict[str, Any]]:
        base_volume = max(800, int(market_overview["monthly_sales_estimate"] * 0.28))
        competition_score = market_overview["competition_score"]
        keywords = []
        seen = set()
        variants = [keyword]
        variants.extend(f"{keyword} {modifier}" for modifier in self._INTENT_MODIFIERS)
        variants.extend(f"{modifier} {keyword}" for modifier in ["best", "cheap", "lightweight"])

        for index, phrase in enumerate(variants):
            normalized = self._normalize_keyword(phrase)
            if normalized in seen:
                continue
            seen.add(normalized)
            intent_bonus = max(0, 18 - index)
            variant_competition = max(8, min(90, competition_score + index * 3 - intent_bonus))
            search_volume = max(300, int(base_volume * (1.12 - min(index, 10) * 0.055)))
            opportunity = round(
                min(10, max(1, (search_volume / 1400) + (100 - variant_competition) / 13)),
                1,
            )
            keywords.append(
                {
                    "keyword": normalized,
                    "search_volume": search_volume,
                    "competition": self._competition_level(variant_competition),
                    "competition_score": round(variant_competition),
                    "opportunity_score": opportunity,
                    "trend": "上升" if opportunity >= 7 else "平稳",
                }
            )

        keywords.sort(key=lambda item: (item["opportunity_score"], item["search_volume"]), reverse=True)
        return keywords[:17]

    def _build_competitor_cards(self, competitors: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cards = []
        for index, competitor in enumerate(competitors[:10], start=1):
            price = self._to_float(competitor.get("price"))
            reviews = self._to_int(competitor.get("review_count"))
            rating = self._to_float(competitor.get("rating"))
            cards.append(
                {
                    "asin": competitor.get("asin") or competitor.get("sku") or "-",
                    "title": competitor.get("title") or competitor.get("asin") or "-",
                    "price": round(price, 2),
                    "rating": round(rating, 1),
                    "review_count": reviews,
                    "url": competitor.get("url") or "",
                    "estimated_monthly_sales": self._estimate_competitor_sales(price, rating, reviews),
                    "badge": "Top Pick" if index == 1 else ("价格带参考" if index <= 3 else ""),
                }
            )
        return cards

    def _build_pricing_advice(self, market_overview: dict[str, Any]) -> dict[str, Any]:
        avg_price = market_overview["avg_price"] or 29.99
        target_min = round(avg_price * 0.88, 2)
        target_max = round(avg_price * 1.08, 2)
        cost_min = round(target_min * 0.25, 2)
        cost_max = round(target_max * 0.40, 2)
        platform_fee_min = target_min * 0.15
        platform_fee_max = target_max * 0.15
        fulfillment_min = target_min * 0.12
        fulfillment_max = target_max * 0.12
        ad_min = target_min * 0.10
        ad_max = target_max * 0.16
        profit_min = round(target_min - cost_max - platform_fee_min - fulfillment_min - ad_max, 2)
        profit_max = round(target_max - cost_min - platform_fee_max - fulfillment_max - ad_min, 2)
        margin_min = round(max(0, profit_min / target_min * 100), 1) if target_min else 0
        margin_max = round(max(0, profit_max / target_max * 100), 1) if target_max else 0

        return {
            "target_price_min": target_min,
            "target_price_max": target_max,
            "cost_min": cost_min,
            "cost_max": cost_max,
            "profit_min": profit_min,
            "profit_max": profit_max,
            "margin_min": margin_min,
            "margin_max": margin_max,
            "notes": [
                "成本区间按目标售价 25%-40% 估算。",
                "平台费、履约费和广告启动成本已按常见比例预留。",
                "若实际采购成本高于建议上限，需要降低目标售价或放弃该方向。",
            ],
        }

    def _build_decision(
        self,
        market_overview: dict[str, Any],
        pricing_advice: dict[str, Any],
    ) -> dict[str, Any]:
        score = market_overview["opportunity_score"]
        margin_min = pricing_advice["margin_min"]
        competition = market_overview["competition"]
        if score >= 7.2 and margin_min >= 18 and competition != "高":
            status = "go"
            label = "可以做"
        elif score >= 5.2 and margin_min >= 10:
            status = "cautious"
            label = "谨慎测试"
        else:
            status = "no_go"
            label = "暂不建议"

        reasons = [
            f"机会评分 {score}/10，竞争度为{competition}。",
            f"建议售价 ${pricing_advice['target_price_min']}-${pricing_advice['target_price_max']}，保守毛利率约 {margin_min}%。",
        ]
        if market_overview["sample_limited"]:
            reasons.append("当前样本偏少，需要补采竞品数据后再下最终判断。")
        if market_overview["avg_reviews"] > 1200:
            reasons.append("竞品评论壁垒偏高，新品冷启动需要差异化切入。")

        return {
            "status": status,
            "label": label,
            "reasons": reasons,
            "next_steps": [
                "先验证蓝海关键词的搜索结果页和广告 CPC。",
                "用目标价格倒推采购、包装、头程和 FBA 成本。",
                "首批上架优先测试 3-5 个低竞争长尾词。",
                "持续采集 TOP 竞品，复核评论壁垒和价格带变化。",
            ],
        }

    def _build_rule_report(
        self,
        *,
        keyword: str,
        marketplace: str,
        market_overview: dict[str, Any],
        keywords: list[dict[str, Any]],
        pricing_advice: dict[str, Any],
        decision: dict[str, Any],
    ) -> str:
        top_keywords = "、".join(item["keyword"] for item in keywords[:5])
        return (
            f"能不能做：{decision['label']}。关键词“{keyword}”在 Amazon {marketplace} 的本地估算月销量约 "
            f"{market_overview['monthly_sales_estimate']:,} 件，均价 ${market_overview['avg_price']}，"
            f"竞争度{market_overview['competition']}，机会评分 {market_overview['opportunity_score']}/10。"
            f"建议目标售价 ${pricing_advice['target_price_min']}-${pricing_advice['target_price_max']}，"
            f"采购成本控制在 ${pricing_advice['cost_min']}-${pricing_advice['cost_max']}，"
            f"利润区间约 ${pricing_advice['profit_min']}-${pricing_advice['profit_max']}。"
            f"怎么做：优先围绕 {top_keywords} 建立首批广告和 Listing 词包；"
            f"主打低竞争细分场景，首批小单测试，目标毛利率不低于 {pricing_advice['margin_min']}%。"
            f"{market_overview['sample_note']}"
        )

    def _polish_report_with_ai(
        self,
        *,
        llm_client: LLMClient,
        rule_report: str,
        keyword: str,
        market_overview: dict[str, Any],
        keywords: list[dict[str, Any]],
        pricing_advice: dict[str, Any],
        decision: dict[str, Any],
    ) -> str:
        payload = {
            "keyword": keyword,
            "market_overview": market_overview,
            "keywords": keywords[:8],
            "pricing_advice": pricing_advice,
            "decision": decision,
            "rule_report": rule_report,
        }
        return llm_client.generate(
            "你是 Amazon 选品顾问。基于给定 JSON 输出一段中文选品决策报告，必须明确能不能做和怎么做，不要使用 Markdown 表格。",
            json.dumps(payload, ensure_ascii=False),
        ).strip()

    def _estimate_monthly_sales(self, competitors: list[dict[str, Any]]) -> int:
        if not competitors:
            return 0
        return int(sum(self._estimate_competitor_sales(
            self._to_float(item.get("price")),
            self._to_float(item.get("rating")),
            self._to_int(item.get("review_count")),
        ) for item in competitors))

    def _estimate_competitor_sales(self, price: float, rating: float, reviews: int) -> int:
        review_signal = math.sqrt(max(reviews, 1)) * 42
        rating_signal = max(rating, 3.6) / 4.5
        price_signal = 1.08 if price and price < 35 else 0.92 if price > 80 else 1.0
        return max(60, int(review_signal * rating_signal * price_signal))

    def _competition_score(
        self,
        *,
        sample_size: int,
        avg_reviews: int,
        avg_rating: float,
        prices: list[float],
    ) -> int:
        sample_score = min(25, sample_size * 3)
        review_score = min(35, avg_reviews / 45)
        rating_score = max(0, (avg_rating - 4.0) * 18)
        price_score = 0
        if len(prices) >= 2 and mean(prices) > 0:
            spread = (max(prices) - min(prices)) / mean(prices)
            price_score = max(0, 18 - spread * 22)
        return round(min(100, sample_score + review_score + rating_score + price_score))

    def _opportunity_score(self, *, monthly_sales: int, competition_score: int, avg_price: float) -> float:
        demand_score = min(4.2, math.log10(max(monthly_sales, 100)) * 1.2)
        competition_bonus = max(0, (100 - competition_score) / 22)
        price_bonus = 1.0 if 18 <= avg_price <= 80 else 0.55
        return round(min(10, max(1, demand_score + competition_bonus + price_bonus)), 1)

    def _competition_level(self, score: float) -> str:
        if score < 40:
            return "低"
        if score < 68:
            return "中"
        return "高"

    def _normalize_keyword(self, keyword: str) -> str:
        return re.sub(r"\s+", " ", keyword.strip().lower())

    def _to_float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _to_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
