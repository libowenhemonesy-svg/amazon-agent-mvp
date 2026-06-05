from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class ProfitCalculationInput:
    product_name: str
    sku: str = ""
    marketplace: str = "US"
    sale_price: float = 0
    landed_cost: float = 0
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


class ProfitCalculator:
    def calculate(self, payload: ProfitCalculationInput) -> dict:
        referral_fee = payload.sale_price * payload.referral_rate
        fba_fee, fba_tier = self._estimate_fba_fee(payload)
        storage_fee = payload.monthly_fixed_cost / payload.monthly_units if payload.monthly_units else 0
        ad_cost = payload.sale_price * payload.ad_acos
        return_cost = payload.sale_price * payload.return_rate * 0.3
        unit_profit = (
            payload.sale_price
            - payload.landed_cost
            - payload.first_leg_freight
            - referral_fee
            - fba_fee
            - storage_fee
            - ad_cost
            - return_cost
        )
        investment_per_unit = payload.landed_cost + payload.first_leg_freight
        q4_multiplier = 1.3 if payload.q4_peak else 1
        monthly_profit = unit_profit * payload.monthly_units * q4_multiplier
        margin = unit_profit / payload.sale_price if payload.sale_price else 0
        roi = unit_profit / investment_per_unit if investment_per_unit else 0
        break_even_units = ceil(payload.monthly_fixed_cost / unit_profit) if unit_profit > 0 else 0

        return {
            "unit_profit": round(unit_profit, 2),
            "margin_percent": round(margin * 100, 1),
            "roi_percent": round(roi * 100, 1),
            "monthly_profit": round(monthly_profit, 2),
            "break_even_units": break_even_units,
            "fba_tier": fba_tier,
            "health": self._health(margin),
            "breakdown": [
                {"label": "售价", "amount": round(payload.sale_price, 2), "type": "income"},
                {"label": "FBA 总费", "amount": round(fba_fee + storage_fee, 2), "type": "cost"},
                {"label": "进货", "amount": round(payload.landed_cost, 2), "type": "cost"},
                {"label": "头程运费", "amount": round(payload.first_leg_freight, 2), "type": "cost"},
                {"label": "平台佣金", "amount": round(referral_fee, 2), "type": "cost"},
                {"label": "广告费", "amount": round(ad_cost, 2), "type": "cost"},
                {"label": "退货成本", "amount": round(return_cost, 2), "type": "cost"},
            ],
            "fees": {
                "referral_fee": round(referral_fee, 2),
                "fulfillment_fee": round(fba_fee, 2),
                "storage_fee": round(storage_fee, 2),
                "ad_cost": round(ad_cost, 2),
                "return_cost": round(return_cost, 2),
            },
            "advice": self._advice(margin, roi, payload),
        }

    def _estimate_fba_fee(self, payload: ProfitCalculationInput) -> tuple[float, str]:
        volume = payload.length_in * payload.width_in * payload.height_in
        dimensional_weight = volume / 139
        billable_weight_lb = max(payload.weight_oz / 16, dimensional_weight)
        longest_side = max(payload.length_in, payload.width_in, payload.height_in)

        if payload.weight_oz <= 16 and volume <= 1152 and longest_side <= 15:
            return 3.65, "小号标准"
        if billable_weight_lb <= 3 and longest_side <= 18:
            return 4.75 + max(0, billable_weight_lb - 1) * 0.5, "大号标准"
        return 8.25 + max(0, billable_weight_lb - 3) * 0.85, "大件"

    def _health(self, margin: float) -> dict:
        if margin >= 0.25:
            return {"status": "healthy", "label": "健康", "message": "毛利率达到 25% 以上"}
        if margin >= 0.15:
            return {"status": "watch", "label": "关注", "message": "毛利率偏紧，建议控制广告和物流成本"}
        return {"status": "risk", "label": "风险", "message": "毛利率低于 15%，需要重新核价"}

    def _advice(self, margin: float, roi: float, payload: ProfitCalculationInput) -> list[str]:
        advice = []
        if margin < 0.25:
            advice.append("优先复核售价、采购成本和 FBA 尺寸分段，避免毛利被固定费用压缩。")
        else:
            advice.append("利润结构健康，可放大流量预算并观察月销规模。")
        if payload.ad_acos > 0.18:
            advice.append("广告 ACoS 偏高，建议拆分精准词和否定词，先守住利润线。")
        if roi < 0.8:
            advice.append("ROI 偏低，建议降低首批采购量或谈判进货成本。")
        if payload.q4_peak:
            advice.append("Q4 旺季已计入销量放大，仍需预留仓储费和补货波动空间。")
        return advice
