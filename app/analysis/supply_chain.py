"""供应链分析本地估算模型。"""
from __future__ import annotations

import re
from typing import Any


class SupplyChainAnalyzer:
    """基于产品、采购量、市场、物流方式和预算生成供应链分析方案。"""

    _CATEGORY_BASE_COST = {
        "kitchen": 5.8,
        "home": 4.6,
        "beauty": 3.9,
        "electronics": 8.5,
        "sports": 6.2,
        "all": 5.2,
    }

    _MARKET_DUTY_RATE = {
        "US": 0.08,
        "CA": 0.09,
        "UK": 0.11,
        "DE": 0.12,
        "JP": 0.07,
    }

    _LOGISTICS_PROFILE = {
        "FBA sea freight": {"label": "FBA 海运", "unit_cost": 1.15, "lead_time_days": 35, "stability": 82},
        "FBA air freight": {"label": "FBA 空运", "unit_cost": 3.6, "lead_time_days": 12, "stability": 88},
        "Express": {"label": "商业快递", "unit_cost": 5.2, "lead_time_days": 7, "stability": 90},
        "Third-party warehouse": {"label": "海外仓", "unit_cost": 1.65, "lead_time_days": 28, "stability": 78},
    }

    def analyze(
        self,
        *,
        product: str,
        purchase_quantity: int,
        marketplace: str = "US",
        logistics_method: str = "FBA sea freight",
        budget: float = 10000,
        category: str = "all",
    ) -> dict[str, Any]:
        product_name = self._clean(product)
        if not product_name:
            raise ValueError("产品不能为空")
        if purchase_quantity <= 0:
            raise ValueError("采购量必须大于 0")
        if budget <= 0:
            raise ValueError("预算必须大于 0")

        marketplace_code = (marketplace or "US").upper()
        category_key = (category or "all").lower()
        logistics = self._LOGISTICS_PROFILE.get(logistics_method, self._LOGISTICS_PROFILE["FBA sea freight"])
        unit_purchase_cost = self._unit_purchase_cost(product_name, purchase_quantity, category_key)
        cost_analysis = self._build_cost_analysis(
            quantity=purchase_quantity,
            unit_purchase_cost=unit_purchase_cost,
            logistics=logistics,
            marketplace=marketplace_code,
        )
        supplier_evaluation = self._build_supplier_evaluation(
            purchase_quantity=purchase_quantity,
            budget=budget,
            cost_analysis=cost_analysis,
        )
        logistics_plan = self._build_logistics_plan(
            method=logistics_method,
            logistics=logistics,
            quantity=purchase_quantity,
            cost_analysis=cost_analysis,
        )
        inventory_plan = self._build_inventory_plan(
            quantity=purchase_quantity,
            logistics=logistics,
            supplier_score=supplier_evaluation["overall_score"],
        )
        cash_flow = self._build_cash_flow(
            budget=budget,
            cost_analysis=cost_analysis,
            inventory_plan=inventory_plan,
        )
        risk_controls = self._build_risk_controls(
            cash_flow=cash_flow,
            logistics_plan=logistics_plan,
            supplier_evaluation=supplier_evaluation,
        )

        return {
            "summary": {
                "product": product_name,
                "purchase_quantity": purchase_quantity,
                "marketplace": marketplace_code,
                "category": category or "all",
                "logistics_method": logistics_method,
                "budget": round(float(budget), 2),
            },
            "cost_analysis": cost_analysis,
            "supplier_evaluation": supplier_evaluation,
            "logistics_plan": logistics_plan,
            "inventory_plan": inventory_plan,
            "cash_flow": cash_flow,
            "risk_controls": risk_controls,
            "report": self._build_report(
                product=product_name,
                marketplace=marketplace_code,
                cost_analysis=cost_analysis,
                supplier_evaluation=supplier_evaluation,
                logistics_plan=logistics_plan,
                inventory_plan=inventory_plan,
                cash_flow=cash_flow,
                risk_controls=risk_controls,
            ),
            "generated_by_ai": False,
        }

    def _build_cost_analysis(
        self,
        *,
        quantity: int,
        unit_purchase_cost: float,
        logistics: dict[str, Any],
        marketplace: str,
    ) -> dict[str, Any]:
        goods_cost = unit_purchase_cost * quantity
        logistics_cost = float(logistics["unit_cost"]) * quantity
        packaging_cost = max(0.22, unit_purchase_cost * 0.045) * quantity
        inspection_cost = max(80, quantity * 0.08)
        duty_rate = self._MARKET_DUTY_RATE.get(marketplace, 0.08)
        duty_cost = (goods_cost + logistics_cost) * duty_rate
        total_cost = goods_cost + logistics_cost + packaging_cost + inspection_cost + duty_cost

        return {
            "unit_purchase_cost": round(unit_purchase_cost, 2),
            "unit_logistics_cost": round(float(logistics["unit_cost"]), 2),
            "goods_cost": round(goods_cost, 2),
            "logistics_cost": round(logistics_cost, 2),
            "packaging_cost": round(packaging_cost, 2),
            "inspection_cost": round(inspection_cost, 2),
            "duty_cost": round(duty_cost, 2),
            "total_cost": round(total_cost, 2),
            "cost_per_unit": round(total_cost / quantity, 2),
        }

    def _build_supplier_evaluation(
        self,
        *,
        purchase_quantity: int,
        budget: float,
        cost_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        budget_room = max(0, min(100, (budget - cost_analysis["total_cost"]) / budget * 100 + 70))
        quantity_score = 92 if purchase_quantity >= 1000 else 78 if purchase_quantity >= 500 else 66
        cost_score = max(50, min(96, round(100 - cost_analysis["cost_per_unit"] * 3)))
        delivery_score = 84 if purchase_quantity >= 1000 else 76
        overall_score = round((budget_room + quantity_score + cost_score + delivery_score) / 4)
        grade = "A" if overall_score >= 88 else "B" if overall_score >= 78 else "C" if overall_score >= 68 else "D"

        return {
            "overall_score": overall_score,
            "grade": grade,
            "dimensions": [
                {"label": "价格稳定性", "score": round(cost_score)},
                {"label": "交付能力", "score": delivery_score},
                {"label": "质检可控", "score": 86},
                {"label": "预算匹配", "score": round(budget_room)},
                {"label": "议价空间", "score": quantity_score},
            ],
            "recommended_terms": [
                "首单 30% 定金，尾款验货后支付",
                "要求出货前 AQL 2.5 抽检报告",
                "约定延迟交付赔付和次品补货条款",
            ],
        }

    def _build_logistics_plan(
        self,
        *,
        method: str,
        logistics: dict[str, Any],
        quantity: int,
        cost_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        lead_time = int(logistics["lead_time_days"])
        buffer_days = 10 if lead_time >= 30 else 5
        batch_count = 3 if quantity >= 2000 else 2 if quantity >= 800 else 1

        return {
            "method": method,
            "label": str(logistics["label"]),
            "lead_time_days": lead_time,
            "buffer_days": buffer_days,
            "batch_count": batch_count,
            "cost_per_unit": cost_analysis["unit_logistics_cost"],
            "stability_score": int(logistics["stability"]),
            "recommendation": self._logistics_recommendation(method, batch_count),
        }

    def _build_inventory_plan(
        self,
        *,
        quantity: int,
        logistics: dict[str, Any],
        supplier_score: int,
    ) -> dict[str, Any]:
        lead_time = int(logistics["lead_time_days"])
        daily_sales_estimate = max(8, round(quantity / 90))
        safety_days = 14 if lead_time >= 30 else 9
        reorder_point = daily_sales_estimate * (lead_time + safety_days)
        first_stock_units = min(quantity, max(round(quantity * 0.55), reorder_point))
        replenish_units = max(round(quantity * 0.35), daily_sales_estimate * 30)
        stockout_risk = "高" if reorder_point > quantity * 0.7 else "中" if supplier_score < 78 else "低"

        return {
            "daily_sales_estimate": daily_sales_estimate,
            "first_stock_units": first_stock_units,
            "replenish_units": replenish_units,
            "reorder_point_units": round(reorder_point),
            "safety_stock_days": safety_days,
            "stockout_risk": stockout_risk,
            "turnover_days": round(first_stock_units / daily_sales_estimate),
            "logic": "按头程时效 + 安全库存天数设置补货点，首批控制在 55%-65% 以降低资金占用。",
        }

    def _build_cash_flow(
        self,
        *,
        budget: float,
        cost_analysis: dict[str, Any],
        inventory_plan: dict[str, Any],
    ) -> dict[str, Any]:
        total_cost = cost_analysis["total_cost"]
        first_stock_ratio = inventory_plan["first_stock_units"] / max(1, inventory_plan["first_stock_units"] + inventory_plan["replenish_units"])
        first_batch_cash = total_cost * min(0.72, max(0.48, first_stock_ratio))
        reserved_cash = max(0, budget - first_batch_cash)
        return {
            "budget": round(budget, 2),
            "budget_usage_rate": round(total_cost / budget * 100, 1),
            "first_batch_cash": round(first_batch_cash, 2),
            "reserved_cash": round(reserved_cash, 2),
            "capital_pressure": "高" if total_cost > budget else "中" if total_cost > budget * 0.82 else "低",
        }

    def _build_risk_controls(
        self,
        *,
        cash_flow: dict[str, Any],
        logistics_plan: dict[str, Any],
        supplier_evaluation: dict[str, Any],
    ) -> list[str]:
        controls = [
            "首单不要一次性全部入 FBA，按首批 + 补货批次拆分，减少滞销资金占用。",
            f"补货点低于 {logistics_plan['lead_time_days']} 天销量覆盖时立即下单，避免头程延迟导致断货。",
            "采购合同写入质检标准、交期、赔付和返工责任，降低供应商履约风险。",
        ]
        if cash_flow["capital_pressure"] == "高":
            controls.append("当前预算压力高，建议降低采购量或改为分批付款后再执行。")
        if supplier_evaluation["overall_score"] < 78:
            controls.append("供应商评分偏低，首单应增加验厂/验货，避免大货质量波动。")
        return controls

    def _build_report(
        self,
        *,
        product: str,
        marketplace: str,
        cost_analysis: dict[str, Any],
        supplier_evaluation: dict[str, Any],
        logistics_plan: dict[str, Any],
        inventory_plan: dict[str, Any],
        cash_flow: dict[str, Any],
        risk_controls: list[str],
    ) -> str:
        return (
            f"针对 {marketplace} 市场的 {product}，本地估算总成本约 ${cost_analysis['total_cost']}，"
            f"单件到仓成本约 ${cost_analysis['cost_per_unit']}。供应商综合评分为 "
            f"{supplier_evaluation['overall_score']} 分（{supplier_evaluation['grade']}），建议采用"
            f"{logistics_plan['label']}，预计头程 {logistics_plan['lead_time_days']} 天，分 "
            f"{logistics_plan['batch_count']} 批执行。首批备货建议 {inventory_plan['first_stock_units']} 件，"
            f"补货点 {inventory_plan['reorder_point_units']} 件，周转周期约 {inventory_plan['turnover_days']} 天。"
            f"资金占用方面，预算使用率约 {cash_flow['budget_usage_rate']}%，首批现金占用约 "
            f"${cash_flow['first_batch_cash']}。核心风控：{risk_controls[0]} {risk_controls[1]} "
            f"该结果为本地估算模型，正式下单前需要用真实供应商报价、装箱数据、关税编码和物流商报价复核。"
        )

    def _unit_purchase_cost(self, product: str, quantity: int, category: str) -> float:
        base = self._CATEGORY_BASE_COST.get(category, self._CATEGORY_BASE_COST["all"])
        complexity = min(2.5, len(self._tokens(product)) * 0.25)
        quantity_discount = 0.86 if quantity >= 3000 else 0.9 if quantity >= 1000 else 0.96
        return round((base + complexity) * quantity_discount, 2)

    def _logistics_recommendation(self, method: str, batch_count: int) -> str:
        if method == "FBA air freight":
            return "适合新品首批测款或紧急补货，成本较高，应控制批量。"
        if method == "Express":
            return "适合小批量急单，建议只用于断货风险补救。"
        if method == "Third-party warehouse":
            return "适合多平台或需要拆批补 FBA 的货品，注意海外仓滞留费。"
        return f"适合中大批量控成本，建议拆成 {batch_count} 批降低到货和滞销风险。"

    def _tokens(self, value: str) -> list[str]:
        return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 1]

    def _clean(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()
