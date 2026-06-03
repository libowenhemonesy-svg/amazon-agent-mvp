"""Amazon 广告优化规则策略生成器。"""
from __future__ import annotations

import re
from typing import Any


class AdOptimizer:
    """基于预算、目标 ACoS 与关键词生成广告投放方案。"""

    _INTENT_MODIFIERS = [
        "portable",
        "rechargeable",
        "mini",
        "travel",
        "personal",
        "quiet",
        "usb",
        "small",
    ]
    _NEGATIVE_MODIFIERS = [
        "cheap",
        "free",
        "used",
        "diy",
        "repair",
        "parts",
        "review",
        "manual",
        "wholesale",
        "industrial",
        "recipe",
        "how to",
    ]

    def optimize(
        self,
        *,
        product_keyword: str,
        daily_budget: float,
        target_acos: float,
        marketplace: str = "US",
        category: str = "all",
        ad_type: str = "Sponsored Products",
    ) -> dict[str, Any]:
        keyword = self._clean(product_keyword).lower()
        if not keyword:
            raise ValueError("产品关键词不能为空")
        if daily_budget <= 0:
            raise ValueError("每日预算必须大于 0")
        if target_acos <= 0 or target_acos >= 1:
            raise ValueError("目标 ACoS 需要使用 0-1 之间的小数")

        budget = round(float(daily_budget), 2)
        acos_percent = round(float(target_acos) * 100)
        baseline_cpc = self._baseline_cpc(keyword, budget, target_acos)
        keyword_bids = self._build_keyword_bids(keyword, baseline_cpc)
        allocation = self._build_budget_allocation(budget, ad_type)
        dayparting = self._build_dayparting_strategy()
        negative_keywords = self._build_negative_keywords(keyword)
        launch_plan = self._build_launch_plan(keyword, budget)
        risk_controls = self._build_risk_controls(acos_percent)

        metrics = {
            "daily_budget": budget,
            "target_acos": acos_percent,
            "estimated_roas": round(1 / target_acos, 1),
            "estimated_clicks": max(1, round(budget / baseline_cpc)),
            "baseline_cpc": baseline_cpc,
        }

        return {
            "marketplace": (marketplace or "US").upper(),
            "category": category or "all",
            "ad_type": ad_type or "Sponsored Products",
            "metrics": metrics,
            "keyword_bids": keyword_bids,
            "negative_keywords": negative_keywords,
            "dayparting_strategy": dayparting,
            "budget_allocation": allocation,
            "launch_plan": launch_plan,
            "optimization_focus": self._build_optimization_focus(keyword, target_acos),
            "risk_controls": risk_controls,
            "report": self._build_report(
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
            ),
            "generated_by_ai": False,
        }

    def _build_keyword_bids(self, keyword: str, baseline_cpc: float) -> list[dict[str, Any]]:
        base_terms = self._keyword_variants(keyword)
        rows = []
        match_cycle = [
            ("精准", 1.2, "高"),
            ("短语", 1.0, "中"),
            ("广泛", 0.78, "中"),
        ]
        for index, term in enumerate(base_terms[:12]):
            match_type, factor, competition = match_cycle[index % len(match_cycle)]
            suggested_bid = round(max(0.25, baseline_cpc * factor), 2)
            rows.append(
                {
                    "keyword": term,
                    "match_type": match_type,
                    "suggested_bid": suggested_bid,
                    "estimated_cpc": round(suggested_bid * 0.82, 2),
                    "competition": competition,
                    "action": "复制",
                }
            )
        return rows

    def _keyword_variants(self, keyword: str) -> list[str]:
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
        for modifier in self._INTENT_MODIFIERS:
            candidates.append(f"{modifier} {noun}")
        return self._dedupe(candidates)

    def _build_negative_keywords(self, keyword: str) -> list[dict[str, str]]:
        noun = (self._tokens(keyword) or [keyword])[-1]
        return [
            {"keyword": f"{modifier} {noun}", "reason": "低购买意图或容易带来无效点击"}
            for modifier in self._NEGATIVE_MODIFIERS
        ][:15]

    def _build_budget_allocation(self, budget: float, ad_type: str) -> dict[str, Any]:
        if ad_type == "Sponsored Brands":
            weights = [("Sponsored Products", 0.55), ("Sponsored Brands", 0.35), ("Sponsored Display", 0.10)]
        elif ad_type == "Sponsored Display":
            weights = [("Sponsored Products", 0.60), ("Sponsored Brands", 0.15), ("Sponsored Display", 0.25)]
        else:
            weights = [("Sponsored Products", 0.70), ("Sponsored Brands", 0.20), ("Sponsored Display", 0.10)]

        items = []
        allocated = 0.0
        for index, (channel, ratio) in enumerate(weights):
            amount = round(budget * ratio, 2)
            if index == len(weights) - 1:
                amount = round(budget - allocated, 2)
            allocated = round(allocated + amount, 2)
            items.append(
                {
                    "channel": channel,
                    "ratio": round(ratio * 100),
                    "daily_budget": amount,
                    "goal": self._channel_goal(channel),
                }
            )
        return {"total_daily_budget": budget, "items": items}

    def _build_dayparting_strategy(self) -> list[dict[str, Any]]:
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

    def _build_launch_plan(self, keyword: str, budget: float) -> list[str]:
        discovery_budget = round(budget * 0.35, 2)
        exact_budget = round(budget * 0.45, 2)
        return [
            f"第 1-3 天用 Auto Discovery 收集搜索词，每日预算约 ${discovery_budget}。",
            f"第 4-7 天把有点击或加购的词转入 Exact/Phrase，核心词围绕 {keyword}。",
            f"第 2 周保留 ACoS 可控词组，Exact 预算提升到约 ${exact_budget}/天。",
            "第 3-4 周增加竞品 ASIN Targeting，并把无订单高点击词加入否定。",
        ]

    def _build_optimization_focus(self, keyword: str, target_acos: float) -> list[str]:
        if target_acos <= 0.2:
            return [
                "优先控 ACoS，Exact 词先小预算验证。",
                "高点击无订单词 10-15 次点击后降价或否定。",
                f"围绕 {keyword} 保留强相关长尾词，减少泛流量。",
            ]
        return [
            "允许前期扩量，Broad/Phrase 可保留更长观察窗口。",
            "每 3 天按 CTR、CVR、ACoS 调整出价。",
            "将有订单搜索词迁移到 Exact 重点放量。",
        ]

    def _build_risk_controls(self, target_acos_percent: int) -> list[str]:
        return [
            f"单词 ACoS 超过 {max(target_acos_percent + 15, 35)}% 且无复购证据时降低 15-25% 出价。",
            "单词点击超过 12 次仍无订单，加入观察名单；超过 20 次无订单建议否定。",
            "新品期避免同时放大预算和提高出价，优先单变量调整。",
            "Listing 转化率偏低时暂停扩量，先优化主图、价格和优惠券。",
        ]

    def _build_report(
        self,
        *,
        keyword: str,
        marketplace: str,
        category: str,
        ad_type: str,
        metrics: dict[str, Any],
        allocation: dict[str, Any],
        keyword_bids: list[dict[str, Any]],
        negative_keywords: list[dict[str, str]],
        launch_plan: list[str],
        risk_controls: list[str],
    ) -> str:
        top_keywords = "、".join(item["keyword"] for item in keyword_bids[:4])
        negatives = "、".join(item["keyword"] for item in negative_keywords[:5])
        sp_budget = next(
            (item["daily_budget"] for item in allocation["items"] if item["channel"] == "Sponsored Products"),
            metrics["daily_budget"],
        )
        return (
            f"针对 Amazon {marketplace} {ad_type}，关键词 {keyword}，建议以目标 ACoS "
            f"{metrics['target_acos']}% 和日预算 ${metrics['daily_budget']} 启动。"
            f"预算先按 SP/SB/SD 分配，其中 Sponsored Products 约 ${sp_budget}/天用于核心转化；"
            f"首批关键词使用 {top_keywords}，基准 CPC 约 ${metrics['baseline_cpc']}，"
            f"精准词高于基准、广泛词低于基准测试。否定词先加入 {negatives} 等低意图词。"
            f"投放节奏：{launch_plan[0]} {launch_plan[1]} {launch_plan[2]} "
            f"风险控制：{risk_controls[0]} {risk_controls[1]} "
            f"该方案为本地估算模型生成，适合做投放前策略草案，正式执行前应结合广告后台真实 CTR、CVR、CPC 和订单数据复核。"
        )

    def _baseline_cpc(self, keyword: str, budget: float, target_acos: float) -> float:
        token_count = max(1, len(self._tokens(keyword)))
        budget_factor = min(1.45, max(0.75, budget / 80))
        acos_factor = min(1.25, max(0.75, target_acos / 0.25))
        return round((0.55 + token_count * 0.12) * budget_factor * acos_factor, 2)

    def _channel_goal(self, channel: str) -> str:
        goals = {
            "Sponsored Products": "承接核心转化与搜索词挖掘",
            "Sponsored Brands": "品牌词和头部词曝光",
            "Sponsored Display": "竞品页面和再营销补量",
        }
        return goals.get(channel, "补充流量")

    def _tokens(self, value: str) -> list[str]:
        return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 1]

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
