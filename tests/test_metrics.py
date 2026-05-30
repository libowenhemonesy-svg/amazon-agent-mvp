from datetime import date, timedelta

from app.metrics.calculator import calculate_daily_metrics


def test_calculate_daily_metrics_builds_sales_ads_and_inventory_metrics():
    run_date = date(2026, 1, 8)
    sales_rows = [
        {"sku": "SKU-001", "date": run_date - timedelta(days=offset), "units_sold": 10 - offset, "sales_amount": 100}
        for offset in range(7)
    ]
    ads_rows = [
        {
            "sku": "SKU-001",
            "date": run_date,
            "impressions": 1000,
            "clicks": 50,
            "spend": 25,
            "ad_orders": 5,
            "ad_sales": 125,
        }
    ]
    inventory_rows = [
        {"sku": "SKU-001", "date": run_date, "available_inventory": 70, "inbound_inventory": 10, "reserved_inventory": 3}
    ]
    sku_rows = [{"sku": "SKU-001", "target_acos": 0.3, "safety_stock_days": 30}]

    metrics = calculate_daily_metrics(run_date, sku_rows, sales_rows, ads_rows, inventory_rows)

    assert metrics[0]["sku"] == "SKU-001"
    assert metrics[0]["units_sold"] == 10
    assert metrics[0]["avg_units_7d"] == 7
    assert metrics[0]["ctr"] == 0.05
    assert metrics[0]["cvr"] == 0.1
    assert metrics[0]["cpc"] == 0.5
    assert metrics[0]["acos"] == 0.2
    assert metrics[0]["inventory_days"] == 10
    assert metrics[0]["lifecycle"] == "stable"
    assert metrics[0]["replenishment_days"] == 20
    assert metrics[0]["sales_trend_7d"] == [4, 5, 6, 7, 8, 9, 10]
    assert metrics[0]["ads_trend_7d"][-1] == {
        "date": "2026-01-08",
        "clicks": 50,
        "spend": 25.0,
        "orders": 5,
        "acos": 0.2,
    }


def test_calculate_daily_metrics_includes_sku_profit_and_quality_modules():
    run_date = date(2026, 1, 8)

    metrics = calculate_daily_metrics(
        run_date,
        sku_rows=[
            {
                "sku": "SKU-001",
                "product_category": "Kitchen",
                "responsible_agent": "Profit-Agent-01",
                "target_acos": 0.3,
                "target_gross_margin": 0.4,
                "safety_stock_days": 30,
            }
        ],
        sales_rows=[{"sku": "SKU-001", "date": run_date, "units_sold": 10, "sales_amount": 300}],
        ads_rows=[],
        inventory_rows=[],
        profit_rows=[
            {
                "sku": "SKU-001",
                "date": run_date,
                "product_cost": 120,
                "platform_fees": 45,
                "logistics_fees": 40,
                "ad_spend": 30,
            }
        ],
        return_rows=[
            {
                "sku": "SKU-001",
                "date": run_date,
                "return_count": 2,
                "return_reason": "质量问题",
                "negative_reviews": 1,
                "rating": 3.8,
            }
        ],
    )

    assert metrics[0]["product_category"] == "Kitchen"
    assert metrics[0]["responsible_agent"] == "Profit-Agent-01"
    assert metrics[0]["gross_margin"] == 0.6
    assert metrics[0]["net_margin"] == 0.2167
    assert metrics[0]["target_gross_margin"] == 0.4
    assert metrics[0]["return_rate"] == 0.2
    assert metrics[0]["return_reason"] == "质量问题"
    assert metrics[0]["rating"] == 3.8
