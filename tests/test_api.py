from datetime import date

from fastapi.testclient import TestClient

from app.main import create_app


def test_frontend_dashboard_is_served():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Amazon Agent 运营台" in response.text
    assert "载入示例并分析" in response.text
    assert "risk-bars" in response.text
    assert "/static/app.js" in response.text


def test_frontend_static_assets_are_served():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    js_response = client.get("/static/app.js")
    css_response = client.get("/static/styles.css")

    assert js_response.status_code == 200
    assert "runAnalysis" in js_response.text
    assert "loadDemo" in js_response.text
    assert "feishuStatus" in js_response.text
    assert "runProductResearch" in js_response.text
    assert "runListingOptimization" in js_response.text
    assert "runAdOptimization" in js_response.text
    assert "runSupplyChainAnalysis" in js_response.text
    assert "saveProfitCalculation" in js_response.text
    assert "runFbaEstimate" in js_response.text
    assert "initPageFromHash" in js_response.text
    assert "getCurrentPageName" in js_response.text
    assert "isPageVisible" in js_response.text
    assert "shouldRefreshDashboardOnLoad" in js_response.text
    assert "pushState" in js_response.text
    assert "aria-current" in js_response.text
    assert "document.title" in js_response.text
    assert "window.scrollTo" in js_response.text
    assert css_response.status_code == 200
    assert ".dashboard" in css_response.text
    assert ".bar-row" in css_response.text
    assert ".research-overview-grid" in css_response.text
    assert ".listing-optimizer-grid" in css_response.text
    assert ".ad-optimizer-grid" in css_response.text
    assert ".supply-chain-grid" in css_response.text
    assert ".profit-calculator-grid" in css_response.text
    assert ".fba-estimator-grid" in css_response.text
    assert ".page.is-visible" in css_response.text
    assert ".nav-item[aria-current=\"page\"]" in css_response.text
    assert ".ui-fluid" in css_response.text
    assert "--surface-raised" in css_response.text
    assert "--accent-blue" in css_response.text
    assert "--accent-amber" in css_response.text
    assert ".app-shell::before" in css_response.text
    assert ".dashboard::before" in css_response.text
    assert ".nav-section-title::after" in css_response.text
    assert ".primary-button::after" in css_response.text
    assert ".summary-card::before" in css_response.text
    assert ".summary-card::after" in css_response.text
    assert ".fba-cost-grid article::before" in css_response.text
    assert ".profit-result-hero::before" in css_response.text
    assert "@media (prefers-reduced-motion: reduce)" in css_response.text
    assert "@media (max-width: 520px)" in css_response.text
    side_nav_block = css_response.text.split(".side-nav {", 1)[1].split("}", 1)[0]
    assert "overflow-y: auto" in side_nav_block


def test_frontend_dashboard_contains_product_research_entry():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "selection-keyword" in response.text
    assert "开始研究" in response.text
    assert "蓝海关键词库" in response.text


def test_frontend_dashboard_contains_listing_optimization_entry():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "page-listing-optimization" in response.text
    assert "Listing 优化" in response.text
    assert "listing-product-description" in response.text


def test_frontend_dashboard_contains_ad_optimization_entry():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "page-ad-optimization" in response.text
    assert "广告优化" in response.text
    assert "ad-product-keyword" in response.text
    assert "生成广告策略" in response.text


def test_ad_optimization_endpoint_generates_strategy():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/ads/optimize",
        json={
            "product_keyword": "portable blender",
            "daily_budget": 50,
            "target_acos": 0.2,
            "marketplace": "US",
            "category": "Kitchen",
            "ad_type": "Sponsored Products",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["daily_spend"] == 50
    assert payload["keyword_bids"]
    assert payload["negative_keywords"]
    assert payload["budget_allocation"]["items"]
    assert payload["dayparting_strategy"]
    assert payload["report"]


def test_ad_optimization_endpoint_rejects_empty_keyword():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/ads/optimize",
        json={"product_keyword": " ", "daily_budget": 50, "target_acos": 0.2},
    )

    assert response.status_code == 400


def test_frontend_dashboard_contains_supply_chain_analysis_entry():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "page-supply-chain" in response.text
    assert "供应链分析" in response.text
    assert "supply-product" in response.text
    assert "分析供应链" in response.text


def test_frontend_dashboard_contains_profit_calculator_entry():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "page-profit-calculator" in response.text
    assert "利润核算" in response.text
    assert "profit-product-name" in response.text
    assert "保存核算" in response.text


def test_frontend_dashboard_contains_fba_estimator_entry():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "page-fba-estimator" in response.text
    assert "FBA 成本估算" in response.text
    assert "fba-weight" in response.text
    assert "FBA Size Tier 完整对照表" in response.text


def test_supply_chain_analysis_endpoint_generates_plan():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/supply-chain/analyze",
        json={
            "product": "portable blender",
            "purchase_quantity": 1200,
            "marketplace": "US",
            "logistics_method": "FBA sea freight",
            "budget": 12000,
            "category": "Kitchen",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cost_analysis"]["total_cost"] > 0
    assert payload["supplier_evaluation"]
    assert payload["logistics_plan"]["method"] == "FBA sea freight"
    assert payload["inventory_plan"]["reorder_point_units"] > 0
    assert payload["risk_controls"]
    assert payload["report"]


def test_supply_chain_analysis_endpoint_rejects_empty_product():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/supply-chain/analyze",
        json={
            "product": " ",
            "purchase_quantity": 1200,
            "marketplace": "US",
            "logistics_method": "FBA sea freight",
            "budget": 12000,
        },
    )

    assert response.status_code == 400


def test_profit_calculation_endpoint_saves_snapshot():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/profit/calculate",
        json={
            "product_name": "Insulated tumbler",
            "sku": "TUMBLER-001",
            "marketplace": "US",
            "sale_price": 29.99,
            "landed_cost": 7.5,
            "first_leg_freight": 1.2,
            "referral_rate": 0.15,
            "weight_oz": 12,
            "length_in": 8,
            "width_in": 6,
            "height_in": 3,
            "ad_acos": 0.15,
            "return_rate": 0.03,
            "monthly_units": 300,
            "monthly_fixed_cost": 300,
            "q4_peak": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] > 0
    assert payload["product_name"] == "Insulated tumbler"
    assert payload["sku"] == "TUMBLER-001"
    assert payload["input"]["sale_price"] == 29.99
    assert payload["result"]["unit_profit"] > 0
    assert payload["result"]["monthly_profit"] > 0
    assert payload["result"]["roi_percent"] > 0
    assert payload["result"]["fba_tier"]
    assert payload["result"]["breakdown"]
    assert payload["result"]["advice"]


def test_profit_calculation_endpoint_rejects_invalid_payload():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    empty_name = client.post(
        "/api/profit/calculate",
        json={"product_name": " ", "sale_price": 29.99, "landed_cost": 7.5},
    )
    invalid_price = client.post(
        "/api/profit/calculate",
        json={"product_name": "Insulated tumbler", "sale_price": 0, "landed_cost": 7.5},
    )

    assert empty_name.status_code == 400
    assert invalid_price.status_code == 400


def test_profit_calculations_endpoint_lists_recent_snapshots():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    first = client.post(
        "/api/profit/calculate",
        json={
            "product_name": "Insulated tumbler",
            "sku": "TUMBLER-001",
            "sale_price": 29.99,
            "landed_cost": 7.5,
            "first_leg_freight": 1.2,
            "monthly_units": 300,
        },
    )
    second = client.post(
        "/api/profit/calculate",
        json={
            "product_name": "Desk organizer",
            "sku": "DESK-001",
            "sale_price": 19.99,
            "landed_cost": 4.5,
            "first_leg_freight": 0.8,
            "monthly_units": 200,
        },
    )
    assert first.status_code == 200
    assert second.status_code == 200

    response = client.get("/api/profit/calculations", params={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    assert payload["items"][0]["product_name"] == "Desk organizer"
    assert payload["items"][1]["product_name"] == "Insulated tumbler"


def test_fba_estimate_endpoint_returns_cost_breakdown():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/fba/estimate",
        json={
            "weight_oz": 12,
            "length_in": 10,
            "width_in": 6,
            "height_in": 2,
            "category": "general",
            "season": "normal",
            "sale_price": 29.99,
            "landed_cost": 8.5,
            "monthly_units": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["size_tier"] == "大号标准"
    assert payload["total_fba_cost"] > 0
    assert payload["fulfillment_fee"] > 0
    assert payload["storage_fee"] > 0
    assert payload["referral_fee"] == 4.5
    assert payload["profit"]["unit_profit"] > 0
    assert payload["tier_table"]


def test_fba_estimate_endpoint_rejects_invalid_dimensions():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/fba/estimate",
        json={"weight_oz": 0, "length_in": 10, "width_in": 6, "height_in": 2},
    )

    assert response.status_code == 400


def test_listing_optimization_endpoint_generates_listing():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/listing/optimize",
        json={
            "product_description": "Portable handheld fan with USB rechargeable battery and low noise motor.",
            "keywords": "portable fan, handheld fan, usb rechargeable fan",
            "marketplace": "US",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["listing"]["title"]
    assert len(payload["listing"]["bullets"]) == 5
    assert payload["quality_score"]["overall_score"] > 0
    assert len(payload["quality_score"]["dimensions"]) == 8
    assert payload["keyword_coverage"]["items"]


def test_listing_optimization_endpoint_rejects_empty_description():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/listing/optimize",
        json={"product_description": " ", "keywords": "portable fan", "marketplace": "US"},
    )

    assert response.status_code == 400


def test_product_research_endpoint_uses_chrome_products():
    app = create_app(
        database_url="sqlite+pysqlite:///:memory:",
        feishu_enabled=False,
        product_research_ai_enabled=False,
    )
    client = TestClient(app)

    submit_response = client.post(
        "/api/chrome/submit",
        json={
            "asin": "B0FAN001",
            "title": "Portable Fan Rechargeable Mini Handheld Fan",
            "price": "$29.99",
            "rating": "4.6 out of 5 stars",
            "review_count": "380 ratings",
            "url": "https://amazon.example/B0FAN001",
        },
    )
    assert submit_response.status_code == 200

    response = client.post(
        "/api/selection/research",
        json={"keyword": "portable fan", "marketplace": "US", "category": "all"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["market_overview"]["sample_size"] == 1
    assert payload["competitors"][0]["asin"] == "B0FAN001"
    assert payload["keywords"]
    assert payload["pricing_advice"]["target_price_min"] > 0
    assert payload["decision"]["status"] in {"go", "cautious", "no_go"}
    assert payload["generated_by_ai"] is False


def test_chrome_submit_parses_localized_price_rating_and_reviews():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    submit_response = client.post(
        "/api/chrome/submit",
        json={
            "asin": "B0AIRPODS",
            "title": "Apple AirPods Pro 2",
            "price": "US$189.99",
            "rating": "4.7 out of 5 stars",
            "review_count": "85,234 ratings",
            "url": "https://amazon.example/B0AIRPODS",
        },
    )

    assert submit_response.status_code == 200
    payload = submit_response.json()
    assert payload["price"] == 189.99
    assert payload["rating"] == 4.7
    assert payload["review_count"] == 85234


def test_product_research_endpoint_rejects_empty_keyword():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/selection/research",
        json={"keyword": "   ", "marketplace": "US", "category": "all"},
    )

    assert response.status_code == 400


def test_demo_sample_endpoint_loads_sample_data_and_runs_analysis():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post("/demo/load-sample")

    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "2026-01-07"
    assert payload["imported"] == {
        "sku": 6,
        "sales": 42,
        "ads": 6,
        "inventory": 6,
        "profit": 6,
        "returns": 6,
    }
    assert payload["metrics_created"] == 6
    assert payload["alerts_created"] >= 1

    report = client.get("/reports/daily", params={"date": "2026-01-07"})
    assert report.status_code == 200
    assert report.json()["risk_count"] == payload["alerts_created"]
    modules = report.json()["report_data"]["module_counts"]
    assert modules["profit"] >= 1
    assert modules["quality"] >= 1

    metrics = client.get("/metrics/daily", params={"date": "2026-01-07"}).json()
    metric_by_sku = {row["sku"]: row for row in metrics}
    assert metric_by_sku["SKU-ADS"]["product_category"] == "Kitchen"
    assert metric_by_sku["SKU-ADS"]["responsible_agent"] == "Ads-Agent-01"
    assert metric_by_sku["SKU-PROFIT"]["gross_margin"] < metric_by_sku["SKU-PROFIT"]["target_gross_margin"]
    assert metric_by_sku["SKU-QUALITY"]["return_rate"] >= 0.1


def test_daily_run_generates_metrics_alerts_agent_recommendations_and_report():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    assert client.post(
        "/imports/sku",
        files={
            "file": (
                "sku.csv",
                b"SKU,Target ACOS,Safety Stock Days,Lifecycle,Replenishment Days\nSKU-001,0.3,30,stable,25\n",
                "text/csv",
            )
        },
    ).status_code == 200
    assert client.post(
        "/imports/sales",
        files={
            "file": (
                "sales.csv",
                (
                    "SKU,Date,Units Sold,Sales Amount\n"
                    "SKU-001,2026-01-01,10,100\n"
                    "SKU-001,2026-01-02,9,100\n"
                    "SKU-001,2026-01-03,8,100\n"
                    "SKU-001,2026-01-04,7,100\n"
                    "SKU-001,2026-01-05,6,100\n"
                    "SKU-001,2026-01-06,5,100\n"
                    "SKU-001,2026-01-07,4,100\n"
                ).encode(),
                "text/csv",
            )
        },
    ).status_code == 200
    assert client.post(
        "/imports/ads",
        files={
            "file": (
                "ads.csv",
                b"SKU,Date,Impressions,Clicks,Spend,Ad Orders,Ad Sales\nSKU-001,2026-01-07,1000,30,45,0,100\n",
                "text/csv",
            )
        },
    ).status_code == 200
    assert client.post(
        "/imports/inventory",
        files={
            "file": (
                "inventory.csv",
                b"SKU,Date,Available Inventory,Inbound Inventory,Reserved Inventory\nSKU-001,2026-01-07,40,0,0\n",
                "text/csv",
            )
        },
    ).status_code == 200

    run_response = client.post("/jobs/daily-run", params={"run_date": str(date(2026, 1, 7))})
    assert run_response.status_code == 200
    assert run_response.json()["alerts_created"] >= 1

    alerts = client.get("/alerts", params={"date": "2026-01-07"}).json()
    assert alerts
    assert alerts[0]["agent_result"]["summary"]
    metrics = client.get("/metrics/daily", params={"date": "2026-01-07"}).json()
    assert metrics[0]["lifecycle"] == "stable"
    assert metrics[0]["replenishment_days"] == 25

    report = client.get("/reports/daily", params={"date": "2026-01-07"}).json()
    assert report["risk_count"] == len(alerts)
    inventory_alerts = [alert for alert in alerts if alert["alert_type"].startswith("inventory")]
    assert len(inventory_alerts) == 1

    reset_response = client.delete("/jobs/daily-run", params={"run_date": "2026-01-07"})
    assert reset_response.status_code == 200
    assert reset_response.json()["deleted_alerts"] >= 1
    assert client.get("/alerts", params={"date": "2026-01-07"}).json() == []


# ==================== 销量监控 ====================


def test_sales_monitor_overview_returns_empty_when_no_data():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/api/sales-monitor/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["alerts"] == []
    assert data["trend"] == []
    assert data["summary"]["alert_count"] == 0
    assert data["summary"]["affected_skus"] == 0


def test_sales_monitor_overview_returns_alerts_after_daily_run():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    # 导入数据：SKU-001 前 7 天销量 100，第 8 天销量 10（触发 sales_drop）
    sku_csv = b"SKU,Title,Price\nSKU-001,Test Product,29.99\n"
    assert client.post("/imports/sku", files={"file": ("sku.csv", sku_csv, "text/csv")}).status_code == 200

    sales_lines = ["SKU,Date,Units Sold,Sales Amount"]
    for d in range(1, 8):
        sales_lines.append(f"SKU-001,2026-01-{d:02d},100,2999.00")
    sales_lines.append("SKU-001,2026-01-08,10,299.90")
    sales_csv = "\n".join(sales_lines).encode()
    assert client.post("/imports/sales", files={"file": ("sales.csv", sales_csv, "text/csv")}).status_code == 200

    ads_csv = b"SKU,Date,Impressions,Clicks,Spend,Ad Orders,Ad Sales\nSKU-001,2026-01-08,1000,30,45,5,150\n"
    assert client.post("/imports/ads", files={"file": ("ads.csv", ads_csv, "text/csv")}).status_code == 200
    inv_csv = b"SKU,Date,Available Inventory,Inbound Inventory,Reserved Inventory\nSKU-001,2026-01-08,100,0,0\n"
    assert client.post("/imports/inventory", files={"file": ("inv.csv", inv_csv, "text/csv")}).status_code == 200

    run_resp = client.post("/jobs/daily-run", params={"run_date": "2026-01-08"})
    assert run_resp.status_code == 200

    overview = client.get("/api/sales-monitor/overview", params={"days": 7, "end_date": "2026-01-08"}).json()
    assert overview["summary"]["alert_count"] >= 1
    assert len(overview["alerts"]) >= 1

    sales_alerts = [a for a in overview["alerts"] if a["alert_type"] == "sales_drop"]
    assert len(sales_alerts) >= 1
    assert sales_alerts[0]["sku"] == "SKU-001"
    assert sales_alerts[0]["severity"] == "high"
    assert "rule_context" in sales_alerts[0]


def test_sales_monitor_metrics_returns_sku_detail():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    sku_csv = b"SKU,Title,Price\nSKU-001,Test,19.99\n"
    assert client.post("/imports/sku", files={"file": ("sku.csv", sku_csv, "text/csv")}).status_code == 200
    sales_csv = b"SKU,Date,Units Sold,Sales Amount\nSKU-001,2026-01-07,50,999.50\n"
    assert client.post("/imports/sales", files={"file": ("sales.csv", sales_csv, "text/csv")}).status_code == 200

    resp = client.get("/api/sales-monitor/metrics/SKU-001", params={"end_date": "2026-01-07"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sku"] == "SKU-001"
    assert len(data["sales"]) == 1
    assert data["sales"][0]["units_sold"] == 50


def test_sales_monitor_page_html_present():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/")
    assert "page-sales-monitor" in response.text
    assert "sm-alert-count" in response.text
    assert "sm-trend-chart" in response.text
