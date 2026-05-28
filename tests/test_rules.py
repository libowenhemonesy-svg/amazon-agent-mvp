from app.rules.engine import evaluate_alert_rules


def test_evaluate_alert_rules_detects_sales_drop_below_half_of_7d_average():
    metrics = [
        {
            "sku": "SKU-001",
            "units_sold": 5,
            "avg_units_7d": 12,
            "avg_units_14d": 11,
            "avg_units_30d": 10,
            "three_day_sales_decline": False,
            "sales_trend_7d": [11, 12, 13, 12, 11, 12, 5],
            "acos": 0.2,
            "target_acos": 0.3,
            "clicks": 10,
            "ad_orders": 1,
            "inventory_days": 60,
            "safety_stock_days": 30,
            "replenishment_days": 20,
        }
    ]

    alerts = evaluate_alert_rules(metrics)

    sales_drop = next(alert for alert in alerts if alert["alert_type"] == "sales_drop")
    assert sales_drop["severity"] == "high"
    assert sales_drop["reason"] == "昨日销量低于近 7 日平均销量 50%"
    assert sales_drop["rule_context"]["observed"] == 5
    assert sales_drop["rule_context"]["baseline"] == 12
    assert sales_drop["rule_context"]["threshold"] == 6
    assert sales_drop["rule_context"]["unit"] == "units"
    assert sales_drop["rule_context"]["decline_ratio"] == 0.5833


def test_evaluate_alert_rules_does_not_use_lifecycle_sales_thresholds():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-GROWTH",
                "units_sold": 55,
                "avg_units_7d": 100,
                "three_day_sales_decline": False,
                "lifecycle": "growth",
                "acos": 0,
                "target_acos": 0.3,
                "clicks": 0,
                "ad_orders": 0,
                "inventory_days": 60,
                "safety_stock_days": 30,
                "replenishment_days": 20,
            }
        ]
    )

    assert not [alert for alert in alerts if alert["alert_type"] == "sales_drop"]


def test_evaluate_alert_rules_detects_sales_ads_and_inventory_alerts():
    metrics = [
        {
            "sku": "SKU-001",
            "units_sold": 4,
            "avg_units_7d": 10,
            "three_day_sales_decline": True,
            "acos": 0.45,
            "target_acos": 0.3,
            "clicks": 30,
            "ad_orders": 0,
            "inventory_days": 15,
            "safety_stock_days": 30,
            "replenishment_days": 20,
        }
    ]

    alerts = evaluate_alert_rules(metrics)

    assert {alert["alert_type"] for alert in alerts} == {
        "sales_drop",
        "sales_declining_3d",
        "acos_high",
        "clicks_without_orders",
        "inventory_below_replenishment",
    }
    assert all(alert["sku"] == "SKU-001" for alert in alerts)
    sales_drop = next(alert for alert in alerts if alert["alert_type"] == "sales_drop")
    assert sales_drop["rule_context"]["observed"] == 4
    assert sales_drop["rule_context"]["baseline"] == 10
    assert sales_drop["rule_context"]["threshold"] == 5


def test_evaluate_alert_rules_avoids_zero_baseline_sales_false_positive():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-ZERO",
                "units_sold": 0,
                "avg_units_7d": 0,
                "three_day_sales_decline": True,
                "lifecycle": "new",
                "acos": 0,
                "target_acos": 0.3,
                "clicks": 0,
                "ad_orders": 0,
                "inventory_days": 60,
                "safety_stock_days": 30,
                "replenishment_days": 20,
            }
        ]
    )

    assert not [alert for alert in alerts if alert["alert_type"].startswith("sales")]


def test_evaluate_alert_rules_uses_custom_replenishment_days():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-INV",
                "units_sold": 10,
                "avg_units_7d": 10,
                "three_day_sales_decline": False,
                "lifecycle": "stable",
                "acos": 0.2,
                "target_acos": 0.3,
                "clicks": 5,
                "ad_orders": 1,
                "inventory_days": 24,
                "safety_stock_days": 30,
                "replenishment_days": 25,
            }
        ]
    )

    assert {alert["alert_type"] for alert in alerts} == {"inventory_below_replenishment"}
    replenishment = next(alert for alert in alerts if alert["alert_type"] == "inventory_below_replenishment")
    assert replenishment["rule_context"]["threshold"] == 25


def test_evaluate_alert_rules_emits_one_inventory_alert_per_sku_when_thresholds_overlap():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-INV",
                "units_sold": 0,
                "avg_units_7d": 0,
                "three_day_sales_decline": False,
                "lifecycle": "stable",
                "acos": 0,
                "target_acos": 0.3,
                "clicks": 0,
                "ad_orders": 0,
                "inventory_days": 0,
                "safety_stock_days": 30,
                "replenishment_days": 25,
            }
        ]
    )

    assert [alert["alert_type"] for alert in alerts] == ["inventory_below_replenishment"]


def test_evaluate_alert_rules_detects_profit_and_quality_alerts():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-PROFIT",
                "units_sold": 10,
                "avg_units_7d": 10,
                "three_day_sales_decline": False,
                "lifecycle": "stable",
                "acos": 0.2,
                "target_acos": 0.3,
                "clicks": 10,
                "ad_orders": 2,
                "inventory_days": 60,
                "safety_stock_days": 30,
                "replenishment_days": 20,
                "gross_margin": 0.22,
                "target_gross_margin": 0.35,
                "return_rate": 0.02,
                "negative_reviews": 0,
                "rating": 4.5,
            },
            {
                "sku": "SKU-QUALITY",
                "units_sold": 10,
                "avg_units_7d": 10,
                "three_day_sales_decline": False,
                "lifecycle": "stable",
                "acos": 0.2,
                "target_acos": 0.3,
                "clicks": 10,
                "ad_orders": 2,
                "inventory_days": 60,
                "safety_stock_days": 30,
                "replenishment_days": 20,
                "gross_margin": 0.45,
                "target_gross_margin": 0.35,
                "return_rate": 0.18,
                "negative_reviews": 2,
                "rating": 3.7,
            },
        ]
    )

    assert {alert["alert_type"] for alert in alerts} == {"profit_below_target", "quality_risk"}
