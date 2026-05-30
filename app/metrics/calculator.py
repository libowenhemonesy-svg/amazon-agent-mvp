from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any


def calculate_daily_metrics(
    run_date: date,
    sku_rows: list[dict[str, Any]],
    sales_rows: list[dict[str, Any]],
    ads_rows: list[dict[str, Any]],
    inventory_rows: list[dict[str, Any]],
    profit_rows: list[dict[str, Any]] | None = None,
    return_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    sales_by_sku = _group_by_sku(sales_rows)
    ads_by_key = {(row["sku"], _as_date(row["date"])): row for row in ads_rows}
    ads_by_sku = _group_by_sku(ads_rows)
    inventory_by_key = {(row["sku"], _as_date(row["date"])): row for row in inventory_rows}
    profit_by_key = {(row["sku"], _as_date(row["date"])): row for row in profit_rows or []}
    return_by_key = {(row["sku"], _as_date(row["date"])): row for row in return_rows or []}

    metrics: list[dict[str, Any]] = []
    for sku_row in sku_rows:
        sku = sku_row["sku"]
        sku_sales = sales_by_sku.get(sku, [])
        current_sales = _row_for_date(sku_sales, run_date)
        ad_row = ads_by_key.get((sku, run_date), {})
        inventory_row = inventory_by_key.get((sku, run_date), {})
        profit_row = profit_by_key.get((sku, run_date), {})
        return_row = return_by_key.get((sku, run_date), {})

        avg_units_7d = _average_units(sku_sales, run_date, 7)
        avg_units_14d = _average_units(sku_sales, run_date, 14)
        avg_units_30d = _average_units(sku_sales, run_date, 30)
        recent_units = [
            _row_for_date(sku_sales, run_date - timedelta(days=offset)).get("units_sold", 0)
            for offset in range(3)
        ]

        clicks = _number(ad_row.get("clicks"))
        impressions = _number(ad_row.get("impressions"))
        spend = _number(ad_row.get("spend"))
        ad_orders = _number(ad_row.get("ad_orders"))
        ad_sales = _number(ad_row.get("ad_sales"))
        available_inventory = _number(inventory_row.get("available_inventory"))
        sales_amount = _number(current_sales.get("sales_amount"))
        product_cost = _number(profit_row.get("product_cost"))
        platform_fees = _number(profit_row.get("platform_fees"))
        logistics_fees = _number(profit_row.get("logistics_fees"))
        profit_ad_spend = _number(profit_row.get("ad_spend"), spend)
        gross_profit = sales_amount - product_cost
        net_profit = gross_profit - platform_fees - logistics_fees - profit_ad_spend
        return_count = _number(return_row.get("return_count"))

        metrics.append(
            {
                "sku": sku,
                "date": run_date,
                "asin": sku_row.get("asin"),
                "platform_link": sku_row.get("platform_link"),
                "store": sku_row.get("store"),
                "marketplace": sku_row.get("marketplace"),
                "product_category": sku_row.get("product_category"),
                "owner": sku_row.get("owner"),
                "responsible_agent": sku_row.get("responsible_agent"),
                "units_sold": int(_number(current_sales.get("units_sold"))),
                "sales_amount": sales_amount,
                "avg_units_7d": avg_units_7d,
                "avg_units_14d": avg_units_14d,
                "avg_units_30d": avg_units_30d,
                "sales_trend_7d": _sales_trend(sku_sales, run_date, 7),
                "ads_trend_7d": _ads_trend(ads_by_sku.get(sku, []), run_date, 7),
                "three_day_sales_decline": recent_units[0] < recent_units[1] < recent_units[2],
                "impressions": int(impressions),
                "clicks": int(clicks),
                "spend": spend,
                "ad_orders": int(ad_orders),
                "ad_sales": ad_sales,
                "ctr": _safe_divide(clicks, impressions),
                "cvr": _safe_divide(ad_orders, clicks),
                "cpc": _safe_divide(spend, clicks),
                "acos": _safe_divide(spend, ad_sales),
                "roas": _safe_divide(ad_sales, spend),
                "available_inventory": int(available_inventory),
                "inbound_inventory": int(_number(inventory_row.get("inbound_inventory"))),
                "reserved_inventory": int(_number(inventory_row.get("reserved_inventory"))),
                "inventory_days": int(_safe_divide(available_inventory, avg_units_7d)),
                "product_cost": product_cost,
                "platform_fees": platform_fees,
                "logistics_fees": logistics_fees,
                "profit_ad_spend": profit_ad_spend,
                "gross_profit": round(gross_profit, 2),
                "net_profit": round(net_profit, 2),
                "gross_margin": _safe_divide(gross_profit, sales_amount),
                "net_margin": _safe_divide(net_profit, sales_amount),
                "return_count": int(return_count),
                "return_rate": _safe_divide(return_count, _number(current_sales.get("units_sold"))),
                "return_reason": return_row.get("return_reason"),
                "negative_reviews": int(_number(return_row.get("negative_reviews"))),
                "rating": _number(return_row.get("rating")),
                "target_acos": _number(sku_row.get("target_acos")),
                "target_gross_margin": _number(sku_row.get("target_gross_margin"), 0.4),
                "safety_stock_days": int(_number(sku_row.get("safety_stock_days"), 30)),
                "replenishment_days": int(_number(sku_row.get("replenishment_days"), 20)),
                "lifecycle": sku_row.get("lifecycle") or "stable",
            }
        )
    return metrics


def _group_by_sku(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["sku"]].append(row)
    return grouped


def _row_for_date(rows: list[dict[str, Any]], target: date) -> dict[str, Any]:
    for row in rows:
        if _as_date(row["date"]) == target:
            return row
    return {}


def _average_units(rows: list[dict[str, Any]], run_date: date, days: int) -> float:
    start = run_date - timedelta(days=days - 1)
    values = [
        _number(row.get("units_sold"))
        for row in rows
        if start <= _as_date(row["date"]) <= run_date
    ]
    return round(sum(values) / len(values), 2) if values else 0


def _sales_trend(rows: list[dict[str, Any]], run_date: date, days: int) -> list[int]:
    return [
        int(_number(_row_for_date(rows, run_date - timedelta(days=offset)).get("units_sold")))
        for offset in reversed(range(days))
    ]


def _ads_trend(rows: list[dict[str, Any]], run_date: date, days: int) -> list[dict[str, Any]]:
    trend: list[dict[str, Any]] = []
    for offset in reversed(range(days)):
        day = run_date - timedelta(days=offset)
        row = _row_for_date(rows, day)
        clicks = _number(row.get("clicks"))
        spend = _number(row.get("spend"))
        orders = _number(row.get("ad_orders"))
        ad_sales = _number(row.get("ad_sales"))
        trend.append(
            {
                "date": day.isoformat(),
                "clicks": int(clicks),
                "spend": spend,
                "orders": int(orders),
                "acos": _safe_divide(spend, ad_sales),
            }
        )
    return trend


def _safe_divide(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0
    return round(numerator / denominator, 4)


def _number(value: Any, default: float = 0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
