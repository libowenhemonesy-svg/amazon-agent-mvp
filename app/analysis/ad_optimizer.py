"""Amazon 广告智能优化器 — 基于真实数据的广告分析与策略生成。

三层架构：
1. 数据分析层 — 从数据库读取真实广告数据，计算趋势和指标
2. 策略引擎层 — 基于数据生成竞价、否定词、预算分配策略
3. 报告生成层 — 输出可执行的优化建议
"""
from __future__ import annotations

import re
import math
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.orm import Session


class AdOptimizer:
    """基于真实数据的广告智能优化器。"""

    # ── 行业基准 ──────────────────────────────────────────────
    BENCHMARKS = {
        "ctr": 0.004,       # CTR 基准 0.4%
        "cvr": 0.10,        # CVR 基准 10%
        "acos": 0.30,       # ACoS 基准 30%
        "cpc": 0.80,        # CPC 基准 $0.80
        "roas": 3.3,        # ROAS 基准 3.3
        "impressions": 1000,  # 日均曝光基准
    }

    # ── 否定词模板 ────────────────────────────────────────────
    _NEGATIVE_MODIFIERS = [
        "cheap", "free", "used", "diy", "repair", "parts",
        "review", "manual", "wholesale", "industrial",
        "recipe", "how to", "homemade", "second hand",
    ]

    # ── 竞价调整幅度 ──────────────────────────────────────────
    _BID_ADJUST_RULES = {
        # (acos_ratio_min, acos_ratio_max, ctr_status, cvr_status) -> (adjust_pct, reason)
        "high_acos_low_cvr": (-0.25, "ACOS高+转化低，大幅降价"),
        "high_acos_ok_cvr": (-0.15, "ACOS高但转化尚可，适度降价"),
        "low_acos_high_cvr": (+0.20, "ACOS低+转化好，加价抢量"),
        "low_acos_ok_cvr": (+0.10, "ACOS低，可以加价测试"),
        "no_orders_high_clicks": (-0.30, "高点击无订单，大幅降价或否定"),
        "low_impressions": (+0.15, "曝光不足，加价获取流量"),
        "stable": (0.00, "指标稳定，维持出价"),
    }

    def __init__(self, session_factory=None):
        """初始化优化器。

        Args:
            session_factory: SQLAlchemy session 工厂，用于读取真实数据。
                             为 None 时退化为纯规则引擎模式。
        """
        self._session_factory = session_factory

    # ═══════════════════════════════════════════════════════════
    #  公开 API
    # ═══════════════════════════════════════════════════════════

    def optimize(
        self,
        *,
        product_keyword: str,
        daily_budget: float,
        target_acos: float,
        marketplace: str = "US",
        category: str = "all",
        ad_type: str = "Sponsored Products",
        sku: str | None = None,
        days: int = 30,
    ) -> dict[str, Any]:
        """生成完整的广告优化方案。

        如果提供了 session_factory 和 sku，会从数据库读取真实数据进行分析。
        否则退化为基于规则的估算模式。
        """
        keyword = self._clean(product_keyword).lower()
        if not keyword:
            raise ValueError("产品关键词不能为空")
        if daily_budget <= 0:
            raise ValueError("每日预算必须大于 0")
        if target_acos <= 0 or target_acos >= 1:
            raise ValueError("目标 ACoS 需要使用 0-1 之间的小数")

        budget = round(float(daily_budget), 2)
        acos_percent = round(float(target_acos) * 100)

        # ── 加载真实数据（如果有） ──
        ads_data = self._load_ads_data(sku, days) if sku else []
        sales_data = self._load_sales_data(sku, days) if sku else []
        sku_info = self._load_sku_info(sku) if sku else {}

        # ── 计算核心指标 ──
        metrics = self._calculate_metrics(ads_data, sales_data, budget, target_acos)

        # ── 竞价优化 ──
        keyword_bids = self._optimize_keyword_bids(keyword, metrics, ads_data)

        # ── 否定词挖掘 ──
        negative_keywords = self._harvest_negative_keywords(keyword, ads_data)

        # ── 预算分配 ──
        allocation = self._build_budget_allocation(budget, ad_type, metrics)

        # ── 分时策略 ──
        dayparting = self._build_dayparting_strategy(ads_data)

        # ── 广告结构建议 ──
        campaign_structure = self._build_campaign_structure(keyword, budget, sku_info)

        # ── ASIN 定向建议 ──
        asin_targeting = self._build_asin_targeting(keyword, sku_info)

        # ── 投放节奏 ──
        launch_plan = self._build_launch_plan(keyword, budget, metrics)

        # ── 风险控制 ──
        risk_controls = self._build_risk_controls(acos_percent, metrics)

        # ── 优化重点 ──
        optimization_focus = self._build_optimization_focus(keyword, target_acos, metrics)

        # ── 趋势分析 ──
        trend_analysis = self._analyze_trends(ads_data, sales_data)

        # ── 生成报告 ──
        report = self._build_report(
            keyword=keyword,
            marketplace=(marketplace or "US").upper(),
            category=category or "all",
            ad_type=ad_type or "Sponsored Products",
            metrics=metrics,
            allocation=allocation,
            keyword_bids=keyword_bids,
            negative_keywords=negative_keywords,
            launch_plan=launch_plan,
            risk_controls=risk_controls,
            trend_analysis=trend_analysis,
            campaign_structure=campaign_structure,
        )

        return {
            "marketplace": (marketplace or "US").upper(),
            "category": category or "all",
            "ad_type": ad_type or "Sponsored Products",
            "metrics": metrics,
            "keyword_bids": keyword_bids,
            "negative_keywords": negative_keywords,
            "dayparting_strategy": dayparting,
            "budget_allocation": allocation,
            "campaign_structure": campaign_structure,
            "asin_targeting": asin_targeting,
            "launch_plan": launch_plan,
            "optimization_focus": optimization_focus,
            "risk_controls": risk_controls,
            "trend_analysis": trend_analysis,
            "report": report,
            "data_source": "database" if ads_data else "estimated",
            "generated_by_ai": False,
        }

    def analyze_sku_ads(self, sku: str, days: int = 30) -> dict[str, Any]:
        """分析单个 SKU 的广告表现，输出诊断报告。

        这是面向 API 的入口，直接返回可渲染的分析结果。
        """
        if not self._session_factory:
            return {"error": "未配置数据库连接，无法分析广告数据"}

        ads_data = self._load_ads_data(sku, days)
        sales_data = self._load_sales_data(sku, days)
        sku_info = self._load_sku_info(sku)

        if not ads_data:
            return {"error": f"SKU {sku} 最近 {days} 天无广告数据"}

        metrics = self._calculate_metrics(ads_data, sales_data, 0, sku_info.get("target_acos", 0.3))
        trend = self._analyze_trends(ads_data, sales_data)
        bid_actions = self._generate_bid_actions(sku, ads_data, metrics, sku_info)
        neg_keywords = self._auto_harvest_negatives(ads_data, metrics)

        health = self._assess_ad_health(metrics, trend)

        return {
            "sku": sku,
            "period_days": days,
            "health": health,
            "metrics": metrics,
            "trend": trend,
            "bid_actions": bid_actions,
            "suggested_negatives": neg_keywords,
            "recommendations": self._generate_recommendations(health, metrics, trend, bid_actions),
        }

    # ═══════════════════════════════════════════════════════════
    #  数据加载层
    # ═══════════════════════════════════════════════════════════

    def _load_ads_data(self, sku: str, days: int) -> list[dict]:
        """从数据库加载广告数据。"""
        from app.db.models import AdsDaily
        session = self._session_factory()
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            stmt = (
                select(AdsDaily)
                .where(AdsDaily.sku == sku, AdsDaily.date >= start_date, AdsDaily.date <= end_date)
                .order_by(AdsDaily.date)
            )
            rows = session.scalars(stmt).all()
            return [
                {
                    "date": r.date,
                    "impressions": r.impressions or 0,
                    "clicks": r.clicks or 0,
                    "spend": r.spend or 0,
                    "ad_orders": r.ad_orders or 0,
                    "ad_sales": r.ad_sales or 0,
                }
                for r in rows
            ]
        finally:
            session.close()

    def _load_sales_data(self, sku: str, days: int) -> list[dict]:
        """从数据库加载销售数据。"""
        from app.db.models import SalesDaily
        session = self._session_factory()
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            stmt = (
                select(SalesDaily)
                .where(SalesDaily.sku == sku, SalesDaily.date >= start_date, SalesDaily.date <= end_date)
                .order_by(SalesDaily.date)
            )
            rows = session.scalars(stmt).all()
            return [
                {"date": r.date, "units_sold": r.units_sold or 0, "sales_amount": r.sales_amount or 0}
                for r in rows
            ]
        finally:
            session.close()

    def _load_sku_info(self, sku: str) -> dict:
        """从数据库加载 SKU 基础信息。"""
        from app.db.models import SkuMaster
        session = self._session_factory()
        try:
            row = session.get(SkuMaster, sku)
            if not row:
                return {}
            return {
                "sku": row.sku,
                "asin": row.asin,
                "title": row.title,
                "price": row.price,
                "rating": row.rating,
                "review_count": row.review_count,
                "lifecycle": row.lifecycle,
                "target_acos": row.target_acos,
                "marketplace": row.marketplace,
                "product_category": row.product_category,
            }
        finally:
            session.close()

    # ═══════════════════════════════════════════════════════════
    #  指标计算层
    # ═══════════════════════════════════════════════════════════

    def _calculate_metrics(
        self,
        ads_data: list[dict],
        sales_data: list[dict],
        budget: float,
        target_acos: float,
    ) -> dict[str, Any]:
        """基于真实数据计算广告核心指标。"""
        if not ads_data:
            return self._estimate_metrics(budget, target_acos)

        total_impressions = sum(d["impressions"] for d in ads_data)
        total_clicks = sum(d["clicks"] for d in ads_data)
        total_spend = sum(d["spend"] for d in ads_data)
        total_ad_orders = sum(d["ad_orders"] for d in ads_data)
        total_ad_sales = sum(d["ad_sales"] for d in ads_data)
        days_count = len(ads_data)

        # 基础指标
        ctr = total_clicks / total_impressions if total_impressions > 0 else 0
        cvr = total_ad_orders / total_clicks if total_clicks > 0 else 0
        acos = total_spend / total_ad_sales if total_ad_sales > 0 else 0
        cpc = total_spend / total_clicks if total_clicks > 0 else 0
        roas = total_ad_sales / total_spend if total_spend > 0 else 0
        cpa = total_spend / total_ad_orders if total_ad_orders > 0 else 0

        # 日均指标
        daily_spend = total_spend / days_count if days_count > 0 else 0
        daily_clicks = total_clicks / days_count if days_count > 0 else 0
        daily_orders = total_ad_orders / days_count if days_count > 0 else 0

        # TACoS（广告花费占总销售额比例）
        total_sales = sum(d.get("sales_amount", 0) for d in sales_data) if sales_data else total_ad_sales
        tacos = total_spend / total_sales if total_sales > 0 else 0

        return {
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_spend": round(total_spend, 2),
            "total_ad_orders": total_ad_orders,
            "total_ad_sales": round(total_ad_sales, 2),
            "total_sales": round(total_sales, 2),
            "days_count": days_count,
            "ctr": round(ctr, 6),
            "cvr": round(cvr, 4),
            "acos": round(acos, 4),
            "cpc": round(cpc, 2),
            "roas": round(roas, 2),
            "cpa": round(cpa, 2),
            "tacos": round(tacos, 4),
            "daily_spend": round(daily_spend, 2),
            "daily_clicks": round(daily_clicks, 1),
            "daily_orders": round(daily_orders, 1),
            "target_acos": round(target_acos * 100) if target_acos < 1 else round(target_acos),
            "ctr_status": self._judge_metric(ctr, self.BENCHMARKS["ctr"], "higher_better"),
            "cvr_status": self._judge_metric(cvr, self.BENCHMARKS["cvr"], "higher_better"),
            "acos_status": self._judge_metric(acos, target_acos if target_acos > 0 else self.BENCHMARKS["acos"], "lower_better"),
            "cpc_status": self._judge_metric(cpc, self.BENCHMARKS["cpc"], "lower_better"),
        }

    def _estimate_metrics(self, budget: float, target_acos: float) -> dict[str, Any]:
        """无真实数据时的估算指标（退化模式）。"""
        token_count = 3  # 默认估算
        baseline_cpc = round((0.55 + token_count * 0.12) * min(1.45, max(0.75, budget / 80)), 2)
        estimated_clicks = max(1, round(budget / baseline_cpc))
        estimated_orders = max(1, round(estimated_clicks * 0.08))

        return {
            "total_impressions": estimated_clicks * 200,
            "total_clicks": estimated_clicks,
            "total_spend": budget,
            "total_ad_orders": estimated_orders,
            "total_ad_sales": round(budget / target_acos, 2) if target_acos > 0 else budget * 3,
            "total_sales": round(budget / target_acos, 2) if target_acos > 0 else budget * 3,
            "days_count": 1,
            "ctr": 0.005,
            "cvr": 0.08,
            "acos": target_acos,
            "cpc": baseline_cpc,
            "roas": round(1 / target_acos, 2) if target_acos > 0 else 3.3,
            "cpa": round(budget / estimated_orders, 2),
            "tacos": target_acos,
            "daily_spend": budget,
            "daily_clicks": estimated_clicks,
            "daily_orders": estimated_orders,
            "target_acos": round(target_acos * 100),
            "ctr_status": "估算",
            "cvr_status": "估算",
            "acos_status": "估算",
            "cpc_status": "估算",
        }

    def _judge_metric(self, actual: float, benchmark: float, direction: str) -> str:
        """判断指标状态：良好/警告/危险。"""
        if benchmark == 0:
            return "无数据"
        ratio = actual / benchmark
        if direction == "higher_better":
            if ratio >= 1.0:
                return "良好"
            if ratio >= 0.7:
                return "警告"
            return "危险"
        else:  # lower_better
            if ratio <= 1.0:
                return "良好"
            if ratio <= 1.5:
                return "警告"
            return "危险"

    # ═══════════════════════════════════════════════════════════
    #  趋势分析层
    # ═══════════════════════════════════════════════════════════

    def _analyze_trends(self, ads_data: list[dict], sales_data: list[dict]) -> dict[str, Any]:
        """分析广告数据趋势，对比近 7 天 vs 前 7 天。"""
        if len(ads_data) < 7:
            return {"status": "insufficient_data", "message": "数据不足 7 天，无法分析趋势"}

        recent_7 = ads_data[-7:]
        prev_7 = ads_data[-14:-7] if len(ads_data) >= 14 else ads_data[:7]

        def _avg(rows: list[dict], key: str) -> float:
            vals = [r[key] for r in rows if r.get(key)]
            return sum(vals) / len(vals) if vals else 0

        def _change(old: float, new: float) -> float:
            return (new - old) / old if old > 0 else 0

        spend_change = _change(_avg(prev_7, "spend"), _avg(recent_7, "spend"))
        clicks_change = _change(_avg(prev_7, "clicks"), _avg(recent_7, "clicks"))
        orders_change = _change(_avg(prev_7, "ad_orders"), _avg(recent_7, "ad_orders"))
        impressions_change = _change(_avg(prev_7, "impressions"), _avg(recent_7, "impressions"))

        # 花费涨但订单不涨 = 恶化
        spend_up_orders_down = spend_change > 0.15 and orders_change < -0.05
        # 曝光涨但点击不涨 = 素材问题
        impressions_up_clicks_down = impressions_change > 0.15 and clicks_change < -0.05
        # 点击涨但订单不涨 = 转化问题
        clicks_up_orders_down = clicks_change > 0.15 and orders_change < -0.05

        # 趋势健康度
        if spend_up_orders_down:
            trend_health = "恶化"
            trend_signal = "广告花费上升但订单未增长，需要优化低效投放"
        elif clicks_up_orders_down:
            trend_health = "转化下降"
            trend_signal = "点击增加但订单未增长，需检查 Listing 转化和搜索词质量"
        elif impressions_up_clicks_down:
            trend_health = "点击率下降"
            trend_signal = "曝光增加但点击未增长，需优化主图和标题"
        elif orders_change > 0.15 and spend_change < 0.05:
            trend_health = "改善"
            trend_signal = "订单增长而花费稳定，广告效率提升"
        else:
            trend_health = "稳定"
            trend_signal = "广告指标波动在正常范围内"

        return {
            "status": "ok",
            "trend_health": trend_health,
            "trend_signal": trend_signal,
            "spend_change_pct": round(spend_change * 100, 1),
            "clicks_change_pct": round(clicks_change * 100, 1),
            "orders_change_pct": round(orders_change * 100, 1),
            "impressions_change_pct": round(impressions_change * 100, 1),
            "signals": {
                "spend_up_orders_down": spend_up_orders_down,
                "impressions_up_clicks_down": impressions_up_clicks_down,
                "clicks_up_orders_down": clicks_up_orders_down,
            },
        }

    # ═══════════════════════════════════════════════════════════
    #  竞价优化层
    # ═══════════════════════════════════════════════════════════

    def _optimize_keyword_bids(
        self, keyword: str, metrics: dict[str, Any], ads_data: list[dict]
    ) -> list[dict[str, Any]]:
        """基于真实指标优化关键词竞价。"""
        baseline_cpc = metrics.get("cpc", self.BENCHMARKS["cpc"])
        if baseline_cpc == 0:
            baseline_cpc = self.BENCHMARKS["cpc"]

        acos = metrics.get("acos", 0.3)
        target_acos = metrics.get("target_acos", 30) / 100
        ctr = metrics.get("ctr", 0.005)
        cvr = metrics.get("cvr", 0.08)

        # 计算竞价调整系数
        if acos > 0 and target_acos > 0:
            acos_ratio = acos / target_acos
        else:
            acos_ratio = 1.0

        if acos_ratio > 1.5 and cvr < 0.05:
            adjust_factor = 0.75  # 高ACOS低转化
        elif acos_ratio > 1.2:
            adjust_factor = 0.85  # ACOS偏高
        elif acos_ratio < 0.7 and cvr > 0.10:
            adjust_factor = 1.20  # 低ACOS高转化
        elif acos_ratio < 0.8:
            adjust_factor = 1.10  # ACOS偏低
        else:
            adjust_factor = 1.00  # 稳定

        variants = self._keyword_variants(keyword)
        rows = []
        match_cycle = [
            ("精准", 1.2, "高"),
            ("短语", 1.0, "中"),
            ("广泛", 0.78, "中"),
        ]

        for index, term in enumerate(variants[:12]):
            match_type, factor, competition = match_cycle[index % len(match_cycle)]
            suggested_bid = round(max(0.25, baseline_cpc * factor * adjust_factor), 2)
            estimated_cpc = round(suggested_bid * 0.82, 2)

            # 竞价建议动作
            if adjust_factor < 0.9:
                action = "降价"
            elif adjust_factor > 1.1:
                action = "加价"
            else:
                action = "维持"

            rows.append({
                "keyword": term,
                "match_type": match_type,
                "suggested_bid": suggested_bid,
                "estimated_cpc": estimated_cpc,
                "competition": competition,
                "action": action,
                "adjust_factor": round(adjust_factor, 2),
            })

        return rows

    def _generate_bid_actions(
        self, sku: str, ads_data: list[dict], metrics: dict[str, Any], sku_info: dict
    ) -> list[dict[str, Any]]:
        """基于真实数据生成竞价调整建议。"""
        if not ads_data:
            return []

        target_acos = sku_info.get("target_acos", 0.30)
        acos = metrics.get("acos", 0)
        cvr = metrics.get("cvr", 0)
        ctr = metrics.get("ctr", 0)
        cpc = metrics.get("cpc", 0)

        actions = []

        # 整体竞价建议
        if acos > 0 and target_acos > 0:
            acos_ratio = acos / target_acos

            if acos_ratio > 1.5:
                actions.append({
                    "scope": "整体",
                    "action": "降价",
                    "幅度": "15-25%",
                    "原因": f"ACOS {acos*100:.1f}% 远超目标 {target_acos*100:.0f}%，需降低整体竞价",
                    "priority": "高",
                })
            elif acos_ratio > 1.2:
                actions.append({
                    "scope": "整体",
                    "action": "适度降价",
                    "幅度": "10-15%",
                    "原因": f"ACOS {acos*100:.1f}% 超过目标 {target_acos*100:.0f}%，需优化",
                    "priority": "中",
                })
            elif acos_ratio < 0.7 and cvr > 0.10:
                actions.append({
                    "scope": "整体",
                    "action": "加价",
                    "幅度": "15-20%",
                    "原因": f"ACOS {acos*100:.1f}% 远低于目标，转化率好，可加价抢量",
                    "priority": "中",
                })

        # CTR 诊断
        if ctr < 0.002:
            actions.append({
                "scope": "创意",
                "action": "优化主图和标题",
                "幅度": "-",
                "原因": f"CTR 仅 {ctr*100:.2f}%，远低于基准 0.4%，曝光没有转化为点击",
                "priority": "高",
            })

        # CVR 诊断
        if cvr < 0.05 and metrics.get("total_clicks", 0) > 50:
            actions.append({
                "scope": "Listing",
                "action": "优化 Listing 转化",
                "幅度": "-",
                "原因": f"CVR 仅 {cvr*100:.1f}%，点击没有转化为订单，需优化 Listing",
                "priority": "高",
            })

        # CPC 趋势
        if cpc > 1.5:
            actions.append({
                "scope": "竞价",
                "action": "降低 CPC",
                "幅度": "考虑长尾词替代",
                "原因": f"平均 CPC ${cpc:.2f} 偏高，可尝试更精准的长尾词降低竞价",
                "priority": "中",
            })

        return actions

    # ═══════════════════════════════════════════════════════════
    #  否定词挖掘层
    # ═══════════════════════════════════════════════════════════

    def _harvest_negative_keywords(
        self, keyword: str, ads_data: list[dict]
    ) -> list[dict[str, str]]:
        """基于模板生成否定关键词列表。"""
        noun = (self._tokens(keyword) or [keyword])[-1]
        return [
            {"keyword": f"{modifier} {noun}", "reason": "低购买意图或容易带来无效点击"}
            for modifier in self._NEGATIVE_MODIFIERS
        ][:15]

    def _auto_harvest_negatives(
        self, ads_data: list[dict], metrics: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """基于真实数据自动挖掘否定关键词。

        逻辑：高点击（>10次）但零订单的搜索词应加入否定。
        注意：当前 AdsDaily 没有搜索词字段，这里基于整体指标推断。
        如果后续增加 SearchTermDaily 表，可以直接接入。
        """
        neg_candidates = []

        # 基于整体指标推断
        avg_cpc = metrics.get("cpc", 0.80)
        total_clicks = metrics.get("total_clicks", 0)
        total_orders = metrics.get("total_ad_orders", 0)

        if total_clicks > 50 and total_orders == 0:
            neg_candidates.append({
                "keyword": "（整体无订单）",
                "reason": f"累计 {total_clicks} 次点击但零订单，建议暂停广告组检查 Listing",
                "severity": "高",
            })

        # 基于否定词模板
        for modifier in self._NEGATIVE_MODIFIERS[:8]:
            neg_candidates.append({
                "keyword": f"*{modifier}*",
                "reason": f"包含 '{modifier}' 的搜索词通常购买意图低",
                "severity": "中",
            })

        return neg_candidates

    # ═══════════════════════════════════════════════════════════
    #  广告结构建议层
    # ═══════════════════════════════════════════════════════════

    def _build_campaign_structure(
        self, keyword: str, budget: float, sku_info: dict
    ) -> dict[str, Any]:
        """推荐广告活动结构。"""
        lifecycle = sku_info.get("lifecycle", "stable")
        review_count = sku_info.get("review_count", 0)

        if lifecycle == "new" or review_count < 50:
            # 新品期：以自动广告为主，收集数据
            return {
                "phase": "新品期",
                "campaigns": [
                    {
                        "name": f"Auto - {keyword}",
                        "type": "自动广告",
                        "budget_pct": 40,
                        "daily_budget": round(budget * 0.40, 2),
                        "purpose": "收集搜索词数据，发现有效关键词",
                        "match_type": "自动",
                        "bid_strategy": "动态竞价-仅降低",
                    },
                    {
                        "name": f"Manual Exact - {keyword}",
                        "type": "手动广告",
                        "budget_pct": 35,
                        "daily_budget": round(budget * 0.35, 2),
                        "purpose": "精准投放核心转化词",
                        "match_type": "精准匹配",
                        "bid_strategy": "动态竞价-仅降低",
                    },
                    {
                        "name": f"Manual Phrase - {keyword}",
                        "type": "手动广告",
                        "budget_pct": 25,
                        "daily_budget": round(budget * 0.25, 2),
                        "purpose": "扩展流量，测试更多搜索词",
                        "match_type": "短语匹配",
                        "bid_strategy": "动态竞价-仅降低",
                    },
                ],
                "tips": [
                    "新品期先跑自动广告 7-14 天收集搜索词",
                    "从自动广告报告中筛选有订单的词加入手动精准",
                    "Review 少于 50 时避免激进竞价",
                ],
            }
        else:
            # 成熟期：精准为主，自动为辅
            return {
                "phase": "成熟期",
                "campaigns": [
                    {
                        "name": f"Exact - {keyword}",
                        "type": "手动广告",
                        "budget_pct": 50,
                        "daily_budget": round(budget * 0.50, 2),
                        "purpose": "核心转化词精准投放",
                        "match_type": "精准匹配",
                        "bid_strategy": "动态竞价-升降",
                    },
                    {
                        "name": f"Phrase - {keyword}",
                        "type": "手动广告",
                        "budget_pct": 25,
                        "daily_budget": round(budget * 0.25, 2),
                        "purpose": "扩展长尾词流量",
                        "match_type": "短语匹配",
                        "bid_strategy": "动态竞价-仅降低",
                    },
                    {
                        "name": f"Auto - {keyword}",
                        "type": "自动广告",
                        "budget_pct": 15,
                        "daily_budget": round(budget * 0.15, 2),
                        "purpose": "持续发现新关键词",
                        "match_type": "自动",
                        "bid_strategy": "动态竞价-仅降低",
                    },
                    {
                        "name": f"SD - {keyword}",
                        "type": "展示广告",
                        "budget_pct": 10,
                        "daily_budget": round(budget * 0.10, 2),
                        "purpose": "竞品页面再营销",
                        "match_type": "ASIN 定向",
                        "bid_strategy": "动态竞价-仅降低",
                    },
                ],
                "tips": [
                    "成熟期以精准匹配为主力，控制 ACOS",
                    "保留自动广告持续挖掘新词",
                    "展示广告用于竞品截流和再营销",
                ],
            }

    # ═══════════════════════════════════════════════════════════
    #  ASIN 定向建议层
    # ═══════════════════════════════════════════════════════════

    def _build_asin_targeting(self, keyword: str, sku_info: dict) -> dict[str, Any]:
        """生成 ASIN 定向建议。"""
        asin = sku_info.get("asin", "")
        price = sku_info.get("price", 0)
        rating = sku_info.get("rating", 0)
        review_count = sku_info.get("review_count", 0)

        strategies = []

        # 价格优势定向
        if price > 0 and rating >= 4.0:
            strategies.append({
                "type": "竞品 ASIN 定向",
                "condition": "选择价格比我高、评分比我低的竞品",
                "reason": f"我方价格 ${price:.2f}，评分 {rating:.1f}，有竞争力",
                "bid_suggestion": "高于关键词竞价 10-20%",
            })

        # 类目定向
        strategies.append({
            "type": "类目定向",
            "condition": "选择同品类但价格区间更高的子类目",
            "reason": "类目定向覆盖面广，适合扩量",
            "bid_suggestion": "低于关键词竞价 20-30%",
        })

        # 品牌定向
        strategies.append({
            "type": "品牌定向",
            "condition": "选择同品类但品牌知名度较低的竞品",
            "reason": "品牌弱的竞品更容易被截流",
            "bid_suggestion": "与关键词竞价持平",
        })

        return {
            "strategies": strategies,
            "tips": [
                "ASIN 定向需要定期更新竞品列表",
                "关注定向 ASIN 的 ACOS，高于目标时及时调整",
                "可以结合 Sponsored Display 做再营销",
            ],
        }

    # ═══════════════════════════════════════════════════════════
    #  预算分配层
    # ═══════════════════════════════════════════════════════════

    def _build_budget_allocation(
        self, budget: float, ad_type: str, metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """基于指标表现分配广告预算。"""
        acos = metrics.get("acos", 0.30)
        cvr = metrics.get("cvr", 0.08)

        # 根据 ACOS 表现调整分配
        if acos < 0.20 and cvr > 0.10:
            # 表现好，可以增加展示广告预算
            weights = [
                ("Sponsored Products", 0.60),
                ("Sponsored Brands", 0.20),
                ("Sponsored Display", 0.20),
            ]
        elif acos > 0.40:
            # 表现差，集中预算到转化最好的 SP
            weights = [
                ("Sponsored Products", 0.80),
                ("Sponsored Brands", 0.10),
                ("Sponsored Display", 0.10),
            ]
        else:
            # 正常分配
            weights = [
                ("Sponsored Products", 0.70),
                ("Sponsored Brands", 0.20),
                ("Sponsored Display", 0.10),
            ]

        items = []
        allocated = 0.0
        for index, (channel, ratio) in enumerate(weights):
            amount = round(budget * ratio, 2)
            if index == len(weights) - 1:
                amount = round(budget - allocated, 2)
            allocated = round(allocated + amount, 2)
            items.append({
                "channel": channel,
                "ratio": round(ratio * 100),
                "daily_budget": amount,
                "goal": self._channel_goal(channel),
            })

        return {"total_daily_budget": budget, "items": items}

    def _channel_goal(self, channel: str) -> str:
        goals = {
            "Sponsored Products": "承接核心转化与搜索词挖掘",
            "Sponsored Brands": "品牌词和头部词曝光",
            "Sponsored Display": "竞品页面和再营销补量",
        }
        return goals.get(channel, "补充流量")

    # ═══════════════════════════════════════════════════════════
    #  分时策略层
    # ═══════════════════════════════════════════════════════════

    def _build_dayparting_strategy(self, ads_data: list[dict]) -> list[dict[str, Any]]:
        """生成分时竞价策略。

        当前 AdsDaily 是日维度数据，无法精确到小时。
        先用行业通用策略，后续如果接入小时数据可以自动优化。
        """
        strategy = []
        for hour in range(24):
            if 8 <= hour <= 11 or 18 <= hour <= 21:
                level = "高峰时段"
                multiplier = 1.25 if hour in {9, 10, 19, 20} else 1.1
            elif 0 <= hour <= 5:
                level = "低谷时段"
                multiplier = 0.5
            else:
                level = "普通时段"
                multiplier = 0.9 if hour in {6, 7, 22, 23} else 1.0
            strategy.append({"hour": hour, "level": level, "bid_multiplier": multiplier})
        return strategy

    # ═══════════════════════════════════════════════════════════
    #  投放节奏层
    # ═══════════════════════════════════════════════════════════

    def _build_launch_plan(
        self, keyword: str, budget: float, metrics: dict[str, Any]
    ) -> list[str]:
        """生成投放节奏建议。"""
        discovery_budget = round(budget * 0.35, 2)
        exact_budget = round(budget * 0.45, 2)
        has_data = metrics.get("days_count", 0) > 7

        if has_data:
            # 有历史数据，给出针对性建议
            acos = metrics.get("acos", 0.30)
            cvr = metrics.get("cvr", 0.08)
            plans = []

            if acos > 0.40:
                plans.append(f"当前 ACoS {acos*100:.0f}% 偏高，第 1 周暂停低效广告组，集中预算到有订单的词。")
            else:
                plans.append(f"当前 ACoS {acos*100:.0f}% 可控，可以逐步放量。")

            if cvr < 0.05:
                plans.append(f"转化率 {cvr*100:.1f}% 偏低，优先优化 Listing 再放量。")
            else:
                plans.append(f"转化率 {cvr*100:.1f}% 良好，可以增加精准词预算。")

            plans.append(f"第 2 周把有订单且 ACoS 可控的词转入 Exact，预算约 ${exact_budget}/天。")
            plans.append("第 3-4 周增加 ASIN 定向和展示广告，扩大流量来源。")
            return plans
        else:
            # 无历史数据，给通用建议
            return [
                f"第 1-3 天用 Auto Discovery 收集搜索词，每日预算约 ${discovery_budget}。",
                f"第 4-7 天把有点击或加购的词转入 Exact/Phrase，核心词围绕 {keyword}。",
                f"第 2 周保留 ACoS 可控词组，Exact 预算提升到约 ${exact_budget}/天。",
                "第 3-4 周增加竞品 ASIN Targeting，并把无订单高点击词加入否定。",
            ]

    # ═══════════════════════════════════════════════════════════
    #  风险控制层
    # ═══════════════════════════════════════════════════════════

    def _build_risk_controls(
        self, target_acos_percent: int, metrics: dict[str, Any]
    ) -> list[str]:
        """生成风险控制建议。"""
        actual_acos = metrics.get("acos", 0.30) * 100
        total_spend = metrics.get("total_spend", 0)
        total_orders = metrics.get("total_ad_orders", 0)

        controls = [
            f"单词 ACoS 超过 {max(target_acos_percent + 15, 35)}% 且无复购证据时降低 15-25% 出价。",
            "单词点击超过 12 次仍无订单，加入观察名单；超过 20 次无订单建议否定。",
            "新品期避免同时放大预算和提高出价，优先单变量调整。",
            "Listing 转化率偏低时暂停扩量，先优化主图、价格和优惠券。",
        ]

        # 基于真实数据的风险提示
        if total_orders > 0 and total_spend > 0:
            cpa = total_spend / total_orders
            if cpa > 20:
                controls.insert(0, f"当前单次订单成本 ${cpa:.2f} 偏高，需要优化竞价或提升转化率。")

        if actual_acos > target_acos_percent * 1.5:
            controls.insert(0, f"当前 ACoS {actual_acos:.0f}% 远超目标 {target_acos_percent}%，建议立即暂停低效广告组。")

        return controls

    # ═══════════════════════════════════════════════════════════
    #  优化重点层
    # ═══════════════════════════════════════════════════════════

    def _build_optimization_focus(
        self, keyword: str, target_acos: float, metrics: dict[str, Any]
    ) -> list[str]:
        """基于指标生成优化重点。"""
        acos = metrics.get("acos", 0.30)
        ctr = metrics.get("ctr", 0.005)
        cvr = metrics.get("cvr", 0.08)

        focuses = []

        # ACOS 优化
        if acos > target_acos:
            focuses.append(f"ACOS {acos*100:.0f}% 超过目标 {target_acos*100:.0f}%，优先降低低效词出价。")
        else:
            focuses.append(f"ACOS {acos*100:.0f}% 低于目标，可以适当放量。")

        # CTR 优化
        if ctr < 0.003:
            focuses.append(f"CTR 仅 {ctr*100:.2f}%，需要优化主图和标题提升点击率。")

        # CVR 优化
        if cvr < 0.05:
            focuses.append(f"CVR {cvr*100:.1f}% 偏低，需优化 Listing 详情页（五点、A+、价格）。")

        # 关键词策略
        focuses.append(f"围绕 {keyword} 保留强相关长尾词，减少泛流量。")

        if target_acos <= 0.20:
            focuses.append("目标 ACoS 较严格，建议 Exact 词先小预算验证。")
        else:
            focuses.append("允许前期扩量，Broad/Phrase 可保留更长观察窗口。")

        return focuses

    # ═══════════════════════════════════════════════════════════
    #  健康度评估层
    # ═══════════════════════════════════════════════════════════

    def _assess_ad_health(
        self, metrics: dict[str, Any], trend: dict[str, Any]
    ) -> dict[str, Any]:
        """评估广告健康度。"""
        scores = {}

        # ACoS 得分 (30分)
        acos = metrics.get("acos", 0.30)
        target_acos = metrics.get("target_acos", 30) / 100
        if target_acos > 0:
            acos_ratio = acos / target_acos
            if acos_ratio <= 0.8:
                scores["acos"] = 30
            elif acos_ratio <= 1.0:
                scores["acos"] = 25
            elif acos_ratio <= 1.3:
                scores["acos"] = 15
            else:
                scores["acos"] = 5
        else:
            scores["acos"] = 15

        # CTR 得分 (25分)
        ctr = metrics.get("ctr", 0.005)
        if ctr >= 0.005:
            scores["ctr"] = 25
        elif ctr >= 0.003:
            scores["ctr"] = 18
        elif ctr >= 0.002:
            scores["ctr"] = 10
        else:
            scores["ctr"] = 5

        # CVR 得分 (25分)
        cvr = metrics.get("cvr", 0.08)
        if cvr >= 0.12:
            scores["cvr"] = 25
        elif cvr >= 0.08:
            scores["cvr"] = 18
        elif cvr >= 0.05:
            scores["cvr"] = 10
        else:
            scores["cvr"] = 5

        # 趋势得分 (20分)
        trend_health = trend.get("trend_health", "稳定")
        if trend_health == "改善":
            scores["trend"] = 20
        elif trend_health == "稳定":
            scores["trend"] = 15
        elif trend_health == "转化下降":
            scores["trend"] = 8
        else:
            scores["trend"] = 5

        total = sum(scores.values())

        if total >= 80:
            level = "green"
            label = "健康"
        elif total >= 55:
            level = "yellow"
            label = "需关注"
        else:
            level = "red"
            label = "需优化"

        return {
            "score": total,
            "level": level,
            "label": label,
            "breakdown": scores,
        }

    # ═══════════════════════════════════════════════════════════
    #  建议生成层
    # ═══════════════════════════════════════════════════════════

    def _generate_recommendations(
        self,
        health: dict[str, Any],
        metrics: dict[str, Any],
        trend: dict[str, Any],
        bid_actions: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """生成优化建议列表。"""
        recs = []

        level = health.get("level", "yellow")
        breakdown = health.get("breakdown", {})

        # ACOS 问题
        if breakdown.get("acos", 15) < 15:
            recs.append({
                "priority": "紧急",
                "category": "ACOS",
                "issue": f"ACOS {metrics.get('acos', 0)*100:.0f}% 超过目标",
                "suggestion": "暂停低效广告组，降低高出价关键词竞价，增加否定词",
            })

        # CTR 问题
        if breakdown.get("ctr", 15) < 10:
            recs.append({
                "priority": "重要",
                "category": "点击率",
                "issue": f"CTR {metrics.get('ctr', 0)*100:.2f}% 偏低",
                "suggestion": "优化主图（白底高清、角度突出卖点），精简标题前置核心关键词",
            })

        # CVR 问题
        if breakdown.get("cvr", 15) < 10:
            recs.append({
                "priority": "重要",
                "category": "转化率",
                "issue": f"CVR {metrics.get('cvr', 0)*100:.1f}% 偏低",
                "suggestion": "优化五点描述、A+ 内容、价格和优惠券，检查差评并改进产品",
            })

        # 趋势问题
        trend_health = trend.get("trend_health", "稳定")
        if trend_health in ("恶化", "转化下降", "点击率下降"):
            recs.append({
                "priority": "紧急",
                "category": "趋势",
                "issue": trend.get("trend_signal", "广告趋势异常"),
                "suggestion": "暂停扩量，排查具体原因（竞品动作、Listing变化、季节性因素）",
            })

        # 竞价建议
        for action in bid_actions[:3]:
            recs.append({
                "priority": action.get("priority", "中"),
                "category": action.get("scope", "竞价"),
                "issue": action.get("原因", ""),
                "suggestion": f"{action.get('action', '')} {action.get('幅度', '')}",
            })

        if not recs:
            recs.append({
                "priority": "优化",
                "category": "综合",
                "issue": "广告表现良好",
                "suggestion": "继续保持，关注竞品动态，持续优化关键词和竞价",
            })

        return recs

    # ═══════════════════════════════════════════════════════════
    #  报告生成层
    # ═══════════════════════════════════════════════════════════

    def _build_report(self, **kwargs) -> str:
        """生成文字报告。"""
        keyword = kwargs["keyword"]
        marketplace = kwargs["marketplace"]
        ad_type = kwargs["ad_type"]
        metrics = kwargs["metrics"]
        allocation = kwargs["allocation"]
        keyword_bids = kwargs["keyword_bids"]
        negative_keywords = kwargs["negative_keywords"]
        launch_plan = kwargs["launch_plan"]
        risk_controls = kwargs["risk_controls"]
        trend = kwargs.get("trend_analysis", {})
        structure = kwargs.get("campaign_structure", {})

        top_keywords = "、".join(item["keyword"] for item in keyword_bids[:4])
        negatives = "、".join(item["keyword"] for item in negative_keywords[:5])
        sp_budget = next(
            (item["daily_budget"] for item in allocation["items"] if item["channel"] == "Sponsored Products"),
            metrics.get("daily_spend", 0),
        )

        data_source = "真实数据" if metrics.get("days_count", 0) > 1 else "估算"
        trend_part = ""
        if trend.get("status") == "ok":
            trend_part = f"近 7 天趋势：{trend.get('trend_health', '稳定')}（{trend.get('trend_signal', '')}）。"

        structure_part = ""
        if structure.get("campaigns"):
            campaign_names = [c["name"] for c in structure["campaigns"][:3]]
            structure_part = f"建议广告结构：{' → '.join(campaign_names)}。"

        return (
            f"针对 Amazon {marketplace} {ad_type}，关键词 {keyword}，"
            f"基于{data_source}分析，目标 ACoS {metrics.get('target_acos', 30)}%，"
            f"实际 ACoS {metrics.get('acos', 0)*100:.1f}%，"
            f"日均花费 ${metrics.get('daily_spend', 0):.2f}，"
            f"日均订单 {metrics.get('daily_orders', 0):.1f} 单。"
            f"{trend_part}"
            f"预算先按 SP/SB/SD 分配，其中 Sponsored Products 约 ${sp_budget}/天用于核心转化；"
            f"首批关键词使用 {top_keywords}，基准 CPC 约 ${metrics.get('cpc', 0.80):.2f}。"
            f"否定词先加入 {negatives} 等低意图词。"
            f"{structure_part}"
            f"投放节奏：{launch_plan[0]} {launch_plan[1]} "
            f"风险控制：{risk_controls[0]} {risk_controls[1]} "
            f"该方案基于{data_source}生成，正式执行前应结合广告后台真实 CTR、CVR、CPC 和订单数据复核。"
        )

    # ═══════════════════════════════════════════════════════════
    #  工具函数
    # ═══════════════════════════════════════════════════════════

    def _keyword_variants(self, keyword: str) -> list[str]:
        """生成关键词变体。"""
        tokens = self._tokens(keyword)
        head = keyword
        noun = tokens[-1] if tokens else keyword
        candidates = [
            head,
            f"best {head}",
            f"{head} for travel",
            f"{head} rechargeable",
            f"mini {noun}",
            f"portable {noun}",
            f"usb {noun}",
            f"personal {noun}",
            f"{noun} for office",
            f"{head} cordless",
            f"{head} quiet",
            f"{head} small",
        ]
        for modifier in ["portable", "rechargeable", "mini", "travel", "personal", "quiet", "usb", "small"]:
            candidates.append(f"{modifier} {noun}")
        return self._dedupe(candidates)

    def _tokens(self, value: str) -> list[str]:
        return [t for t in re.findall(r"[a-z0-9]+", value.lower()) if len(t) > 1]

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        output = []
        for value in values:
            cleaned = self._clean(value).lower()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                output.append(cleaned)
        return output

    def _clean(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()
