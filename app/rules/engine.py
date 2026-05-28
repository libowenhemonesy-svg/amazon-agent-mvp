from __future__ import annotations

from typing import Any


def evaluate_alert_rules(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for row in metrics:
        sku = row["sku"]
        date_value = row.get("date")
        avg_units_7d = row.get("avg_units_7d", 0)
        units_sold = row.get("units_sold", 0)
        sales_drop_threshold = round(avg_units_7d * 0.5, 2)

        if avg_units_7d and units_sold < sales_drop_threshold:
            alerts.append(
                _alert(
                    date_value,
                    sku,
                    "sales_drop",
                    "high",
                    "昨日销量低于近 7 日平均销量 50%",
                    observed=units_sold,
                    baseline=avg_units_7d,
                    threshold=sales_drop_threshold,
                    unit="units",
                    extra_context={
                        "decline_ratio": round((avg_units_7d - units_sold) / avg_units_7d, 4),
                    },
                )
            )
        if avg_units_7d and row.get("three_day_sales_decline"):
            alerts.append(
                _alert(
                    date_value,
                    sku,
                    "sales_declining_3d",
                    "medium",
                    "连续 3 日销量下降",
                    observed=row.get("sales_trend_7d", [])[-3:],
                    baseline="3-day trend",
                    threshold="strictly declining",
                    unit="units",
                )
            )
        if row.get("target_acos", 0) and row.get("acos", 0) > row["target_acos"] + 0.1:
            alerts.append(
                _alert(
                    date_value,
                    sku,
                    "acos_high",
                    "medium",
                    "ACOS 高于目标值 10 个百分点以上",
                    observed=row.get("acos", 0),
                    baseline=row.get("target_acos", 0),
                    threshold=round(row.get("target_acos", 0) + 0.1, 4),
                    unit="ratio",
                )
            )
        if row.get("clicks", 0) >= 20 and row.get("ad_orders", 0) == 0:
            alerts.append(
                _alert(
                    date_value,
                    sku,
                    "clicks_without_orders",
                    "medium",
                    "点击超过阈值但无订单",
                    observed=row.get("clicks", 0),
                    baseline=row.get("ad_orders", 0),
                    threshold=20,
                    unit="clicks",
                )
            )
        ad_trend = row.get("ads_trend_7d", [])[-3:]
        if _spend_increasing_without_orders_growth(ad_trend):
            spend_values = [entry.get("spend", 0) for entry in ad_trend]
            order_values = [entry.get("orders", 0) for entry in ad_trend]
            alerts.append(
                _alert(
                    date_value,
                    sku,
                    "ad_spend_increasing_without_orders_growth",
                    "medium",
                    "近 3 日广告花费持续增加，但广告订单未同步增长",
                    observed={
                        "spend": spend_values,
                        "orders": order_values,
                    },
                    baseline={
                        "spend": spend_values[0],
                        "orders": order_values[0],
                    },
                    threshold="spend strictly increasing and orders not increasing",
                    unit="mixed",
                )
            )
        inventory_days = row.get("inventory_days", 0)
        safety_stock_days = row.get("safety_stock_days", 30)
        replenishment_days = row.get("replenishment_days", 20)
        if inventory_days < replenishment_days:
            alerts.append(
                _alert(
                    date_value,
                    sku,
                    "inventory_below_replenishment",
                    "high",
                    f"可售天数低于补货周期 {replenishment_days} 天",
                    observed=inventory_days,
                    baseline=replenishment_days,
                    threshold=replenishment_days,
                    unit="days",
                )
            )
        elif inventory_days < safety_stock_days:
            alerts.append(
                _alert(
                    date_value,
                    sku,
                    "inventory_below_safety",
                    "high",
                    "可售天数低于安全库存天数",
                    observed=inventory_days,
                    baseline=safety_stock_days,
                    threshold=safety_stock_days,
                    unit="days",
                )
            )
        target_gross_margin = row.get("target_gross_margin", 0)
        gross_margin = row.get("gross_margin", 0)
        if target_gross_margin and gross_margin and gross_margin < target_gross_margin:
            alerts.append(
                _alert(
                    date_value,
                    sku,
                    "profit_below_target",
                    "medium",
                    "毛利率低于目标毛利率",
                    observed=gross_margin,
                    baseline=target_gross_margin,
                    threshold=target_gross_margin,
                    unit="ratio",
                )
            )
        return_rate = row.get("return_rate", 0)
        negative_reviews = row.get("negative_reviews", 0)
        rating = row.get("rating", 0)
        if return_rate >= 0.1 or negative_reviews >= 2 or (rating and rating < 4):
            alerts.append(
                _alert(
                    date_value,
                    sku,
                    "quality_risk",
                    "medium",
                    "退货、差评或评分触发质量风险",
                    observed={
                        "return_rate": return_rate,
                        "negative_reviews": negative_reviews,
                        "rating": rating,
                    },
                    baseline="return_rate<0.1, negative_reviews<2, rating>=4",
                    threshold={"return_rate": 0.1, "negative_reviews": 2, "rating": 4},
                    unit="mixed",
                )
            )
    return alerts


def _spend_increasing_without_orders_growth(ad_trend: list[dict[str, Any]]) -> bool:
    if len(ad_trend) < 3:
        return False
    spend_values = [float(entry.get("spend", 0) or 0) for entry in ad_trend]
    order_values = [int(entry.get("orders", 0) or 0) for entry in ad_trend]
    spend_increasing = spend_values[0] < spend_values[1] < spend_values[2]
    orders_not_growing = order_values[-1] <= order_values[0]
    return spend_values[-1] > 0 and spend_increasing and orders_not_growing


def _alert(
    date_value: Any,
    sku: str,
    alert_type: str,
    severity: str,
    reason: str,
    *,
    observed: Any,
    baseline: Any,
    threshold: Any,
    unit: str,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rule_context = {
        "observed": observed,
        "baseline": baseline,
        "threshold": threshold,
        "unit": unit,
    }
    if extra_context:
        rule_context.update(extra_context)
    return {
        "date": date_value,
        "sku": sku,
        "alert_type": alert_type,
        "severity": severity,
        "reason": reason,
        "rule_context": rule_context,
    }
