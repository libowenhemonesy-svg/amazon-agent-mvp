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
    assert css_response.status_code == 200
    assert ".dashboard" in css_response.text
    assert ".bar-row" in css_response.text


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
