from __future__ import annotations

from dataclasses import dataclass


CATEGORY_REFERRAL_RATES = {
    "general": 0.15,
    "electronics": 0.08,
    "apparel": 0.17,
    "beauty": 0.15,
    "grocery": 0.15,
}


TIER_TABLE = [
    {
        "tier": "小号标准",
        "weight_range": "≤ 16 oz (1 lb)",
        "size_limit": "15 × 12 × 0.75 in",
        "fee_range": "$3.06 - $3.43",
    },
    {
        "tier": "大号标准",
        "weight_range": "≤ 20 lb",
        "size_limit": "18 × 14 × 8 in",
        "fee_range": "$3.43 - $6.20",
    },
    {
        "tier": "大号大件",
        "weight_range": "≤ 50 lb",
        "size_limit": "longest ≤ 59 in, length + girth ≤ 130 in",
        "fee_range": "$9.61",
    },
    {
        "tier": "超大件 0-50 磅",
        "weight_range": "≤ 50 lb",
        "size_limit": "超出 large bulky 限制",
        "fee_range": "$26.33",
    },
    {
        "tier": "超大件 50-70 磅",
        "weight_range": "50 - 70 lb",
        "size_limit": "重型物件",
        "fee_range": "$40.12",
    },
    {
        "tier": "超大件 70-150 磅",
        "weight_range": "70 - 150 lb",
        "size_limit": "重型物件",
        "fee_range": "$54.81",
    },
]


@dataclass(frozen=True)
class FbaEstimateInput:
    weight_oz: float
    length_in: float
    width_in: float
    height_in: float
    category: str = "general"
    season: str = "normal"
    sale_price: float = 0
    landed_cost: float = 0
    monthly_units: int = 1


class FbaEstimator:
    def estimate(self, payload: FbaEstimateInput) -> dict:
        size_tier = self._size_tier(payload)
        fulfillment_fee = self._fulfillment_fee(payload, size_tier)
        storage_fee = self._storage_fee(payload)
        referral_rate = CATEGORY_REFERRAL_RATES.get(payload.category, CATEGORY_REFERRAL_RATES["general"])
        referral_fee = payload.sale_price * referral_rate if payload.sale_price else 0
        total_fba_cost = fulfillment_fee + storage_fee + referral_fee
        unit_profit = payload.sale_price - payload.landed_cost - total_fba_cost if payload.sale_price else 0
        margin = unit_profit / payload.sale_price if payload.sale_price else 0

        return {
            "size_tier": size_tier,
            "total_fba_cost": round(total_fba_cost, 2),
            "fulfillment_fee": round(fulfillment_fee, 2),
            "storage_fee": round(storage_fee, 2),
            "referral_fee": round(referral_fee, 2),
            "referral_rate_percent": round(referral_rate * 100, 1),
            "season": payload.season,
            "storage_monthly_total": round(storage_fee * payload.monthly_units, 2),
            "billable_weight_lb": round(self._billable_weight_lb(payload), 2),
            "cubic_feet": round(self._cubic_feet(payload), 4),
            "profit": {
                "unit_profit": round(unit_profit, 2),
                "margin_percent": round(margin * 100, 1),
                "landed_cost": round(payload.landed_cost, 2),
            },
            "tier_table": TIER_TABLE,
            "formula": (
                f"Fulfillment ${fulfillment_fee:.2f} + Storage ${storage_fee:.2f}"
                + (f" + Referral ${referral_fee:.2f}" if payload.sale_price else "")
            ),
        }

    def _size_tier(self, payload: FbaEstimateInput) -> str:
        sorted_dimensions = sorted([payload.length_in, payload.width_in, payload.height_in], reverse=True)
        longest, median, shortest = sorted_dimensions
        weight_lb = payload.weight_oz / 16
        length_plus_girth = longest + 2 * (median + shortest)

        if payload.weight_oz <= 16 and longest <= 15 and median <= 12 and shortest <= 0.75:
            return "小号标准"
        if weight_lb <= 20 and longest <= 18 and median <= 14 and shortest <= 8:
            return "大号标准"
        if weight_lb <= 50 and longest <= 59 and length_plus_girth <= 130:
            return "大号大件"
        if weight_lb <= 50:
            return "超大件 0-50 磅"
        if weight_lb <= 70:
            return "超大件 50-70 磅"
        return "超大件 70-150 磅"

    def _fulfillment_fee(self, payload: FbaEstimateInput, size_tier: str) -> float:
        billable_weight = self._billable_weight_lb(payload)
        if size_tier == "小号标准":
            return 3.06 if payload.weight_oz <= 4 else 3.43
        if size_tier == "大号标准":
            return min(6.2, 3.43 + max(0, billable_weight - 1) * 0.55)
        if size_tier == "大号大件":
            return 9.61 + max(0, billable_weight - 1) * 0.38
        if size_tier == "超大件 0-50 磅":
            return 26.33
        if size_tier == "超大件 50-70 磅":
            return 40.12
        return 54.81

    def _storage_fee(self, payload: FbaEstimateInput) -> float:
        monthly_rate = 0.87 if payload.season == "peak" else 0.78
        return self._cubic_feet(payload) * monthly_rate

    def _billable_weight_lb(self, payload: FbaEstimateInput) -> float:
        dimensional_weight = payload.length_in * payload.width_in * payload.height_in / 139
        return max(payload.weight_oz / 16, dimensional_weight)

    def _cubic_feet(self, payload: FbaEstimateInput) -> float:
        return payload.length_in * payload.width_in * payload.height_in / 1728
