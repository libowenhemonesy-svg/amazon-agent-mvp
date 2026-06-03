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
    assert "window.scrollTo" in js_response.text
    assert css_response.status_code == 200
    assert ".dashboard" in css_response.text
    assert ".bar-row" in css_response.text
    assert ".research-overview-grid" in css_response.text
    assert ".listing-optimizer-grid" in css_response.text
    assert ".ad-optimizer-grid" in css_response.text
    assert ".supply-chain-grid" in css_response.text
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
    assert payload["metrics"]["daily_budget"] == 50
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
