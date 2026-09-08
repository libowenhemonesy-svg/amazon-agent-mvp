from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.models import AdsDaily, InventoryDaily, SalesDaily
from app.db.repository import upsert_daily_rows, upsert_sku_rows
from app.deps import get_session_factory
from app.routes import settings as settings_route


def create_app(*args, **kwargs):
    """仅在需要完整生产应用的测试中加载工厂，避免 settings 测试初始化 RAG。"""
    from app.main import create_app as app_factory

    return app_factory(*args, **kwargs)


def seed_operational_data(
    *,
    sku_rows: list[dict],
    sales_rows: list[dict] | None = None,
    ads_rows: list[dict] | None = None,
    inventory_rows: list[dict] | None = None,
) -> None:
    with get_session_factory()() as session:
        upsert_sku_rows(session, sku_rows)
        if sales_rows:
            upsert_daily_rows(session, SalesDaily, sales_rows)
        if ads_rows:
            upsert_daily_rows(session, AdsDaily, ads_rows)
        if inventory_rows:
            upsert_daily_rows(session, InventoryDaily, inventory_rows)


def test_frontend_dashboard_is_served():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Amazon Agent 运营台" in response.text
    assert "载入示例并分析" in response.text
    assert "risk-bars" in response.text
    assert "/static/app.js" in response.text
    assert "image-card-20260625" in response.text


def test_data_import_routes_are_not_registered():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post("/imports/sku")

    assert response.status_code == 404


def test_removed_battlefield_and_diagnosis_routes_are_not_registered():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    assert client.get("/api/battlefield/analyze").status_code == 404
    assert client.get("/api/diagnosis/run").status_code == 404


def _mcp_source_payload(name: str, capability: str, tool: str) -> dict:
    return {
        "name": name,
        "url": f"https://mcp.example.com/{tool}",
        "transport": "streamable_http",
        "priority": 10,
        "enabled": True,
        "capabilities": {capability: {"tool": tool}},
    }


def test_admin_can_create_multiple_mcp_sources(client_as_admin, monkeypatch):
    credential_env = {}
    monkeypatch.setattr(
        settings_route,
        "get_credential_store",
        lambda: settings_route.EnvCredentialStore(
            credential_env, lambda updates: credential_env.update(updates)
        ),
    )
    first_payload = _mcp_source_payload("卖家精灵", "keyword_expand", "keyword_research")
    first_payload.update(
        {"api_key": "first-secret", "headers": {"X-Workspace": "private-workspace"}}
    )

    first = client_as_admin.post("/api/settings/mcp-sources", json=first_payload)
    second = client_as_admin.post(
        "/api/settings/mcp-sources",
        json=_mcp_source_payload("趋势数据", "keyword_trend", "trend"),
    )
    listed = client_as_admin.get("/api/settings/mcp-sources")

    assert first.status_code == second.status_code == 201
    assert len(listed.json()["items"]) == 2
    assert first.json()["credentials_configured"] is True
    serialized = listed.text
    assert "first-secret" not in serialized
    assert "private-workspace" not in serialized
    assert "api_key" not in serialized
    assert "headers" not in serialized


def test_non_admin_cannot_manage_mcp_sources(client_as_user):
    assert client_as_user.get("/api/settings/mcp-sources").status_code == 403
    response = client_as_user.post(
        "/api/settings/mcp-sources",
        json=_mcp_source_payload("市场数据", "keyword_expand", "keyword_research"),
    )
    assert response.status_code == 403
    assert client_as_user.patch("/api/settings/mcp-sources/1", json={"enabled": False}).status_code == 403
    assert client_as_user.post("/api/settings/mcp-sources/1/test").status_code == 403


@pytest.mark.parametrize(
    ("url", "input_value"),
    [
        ("https://mcp.example.com/mcp?api_key=demo-secret", "demo-secret"),
        ("https://mcp.example.com/mcp?client_secret=demo-secret", "demo-secret"),
        ("https://mcp.example.com/mcp?foo=bar", "bar"),
        ("https://demo-user:demo-secret@mcp.example.com/mcp", "demo-secret"),
        ("https://mcp.example.com/mcp#fragment-secret", "fragment-secret"),
    ],
)
def test_mcp_source_rejects_url_metadata_without_echoing_it(
    client_as_admin, url, input_value
):
    payload = _mcp_source_payload("危险地址", "keyword_expand", "keyword_research")
    payload["url"] = url

    response = client_as_admin.post("/api/settings/mcp-sources", json=payload)
    listed = client_as_admin.get("/api/settings/mcp-sources")

    assert response.status_code == 422
    assert response.json()["detail"] == "MCP 地址不能包含查询参数、凭据或片段"
    assert input_value not in response.text
    assert url not in response.text
    assert input_value not in listed.text
    assert listed.json()["items"] == []


def test_mcp_source_accepts_plain_path_url(client_as_admin):
    response = client_as_admin.post(
        "/api/settings/mcp-sources",
        json=_mcp_source_payload("普通地址", "keyword_expand", "keyword_research"),
    )

    assert response.status_code == 201
    assert response.json()["url"] == "https://mcp.example.com/keyword_research"


def test_mcp_source_rejects_unsupported_sse_transport(client_as_admin):
    payload = _mcp_source_payload("旧传输", "keyword_expand", "keyword_research")
    payload["transport"] = "sse"

    response = client_as_admin.post("/api/settings/mcp-sources", json=payload)

    assert response.status_code == 422


def test_mcp_settings_frontend_marks_caught_connection_failure():
    javascript = (settings_route.Path.cwd() / "app" / "static" / "app.js").read_text(
        encoding="utf-8"
    )

    assert 'source.connectionStatus = "连接异常"' in javascript


def test_blank_credentials_update_preserves_existing_mcp_credentials(
    client_as_admin, monkeypatch
):
    credential_env = {}
    monkeypatch.setattr(
        settings_route,
        "get_credential_store",
        lambda: settings_route.EnvCredentialStore(
            credential_env, lambda updates: credential_env.update(updates)
        ),
    )
    payload = _mcp_source_payload("市场数据", "keyword_expand", "keyword_research")
    payload["api_key"] = "saved-secret"
    created = client_as_admin.post("/api/settings/mcp-sources", json=payload)

    response = client_as_admin.patch(
        f"/api/settings/mcp-sources/{created.json()['id']}",
        json={"priority": 20, "api_key": "", "headers": {}},
    )

    assert response.status_code == 200
    assert response.json()["priority"] == 20
    assert response.json()["credentials_configured"] is True
    assert credential_env[f"MCP_SOURCE_{created.json()['id']}_API_KEY"] == "saved-secret"


def test_mcp_source_connection_test_reports_missing_tool_names_only(
    client_as_admin, monkeypatch
):
    class FakeClient:
        async def list_tools(self):
            return {
                "tools": [
                    {
                        "name": "keyword_research",
                        "description": "internal description",
                        "inputSchema": {"token": "must-not-leak"},
                    }
                ]
            }

    monkeypatch.setattr(settings_route, "build_mcp_client", lambda source, headers: FakeClient())
    created = client_as_admin.post(
        "/api/settings/mcp-sources",
        json={
            **_mcp_source_payload("研究数据", "keyword_expand", "keyword_research"),
            "capabilities": {
                "keyword_expand": {"tool": "keyword_research"},
                "keyword_trend": {"tool": "trend"},
            },
        },
    )

    response = client_as_admin.post(
        f"/api/settings/mcp-sources/{created.json()['id']}/test"
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "message": "连接成功，但能力映射缺少工具",
        "tools": ["keyword_research"],
        "missing_mappings": {"keyword_trend": "trend"},
    }
    assert "must-not-leak" not in response.text


def test_frontend_static_assets_are_served(client):
    js_response = client.get("/static/app.js")
    css_response = client.get("/static/styles.css")
    selection_js = client.get("/static/selection-workbench.js")
    selection_css = client.get("/static/selection-workbench.css")

    assert js_response.status_code == 200
    assert "runAnalysis" in js_response.text
    assert "loadDemo" in js_response.text
    assert "feishuStatus" in js_response.text
    assert selection_js.status_code == 200
    assert "SelectionWorkbench" in selection_js.text
    assert selection_css.status_code == 200
    assert ".selection-workbench" in selection_css.text
    assert "runListingOptimization" in js_response.text
    assert "runAdOptimization" in js_response.text
    assert "runSupplyChainAnalysis" in js_response.text
    assert "saveProfitCalculation" in js_response.text
    assert "runFbaEstimate" in js_response.text
    assert "addImageMessage" in js_response.text
    assert "case \"image\"" in js_response.text
    assert "sseBuffer" in js_response.text
    assert "processSseBlock" in js_response.text
    assert "renderGeneratedImageLinks" in js_response.text
    assert "data-url" in js_response.text
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
    assert ".generated-image-card" in css_response.text
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


def test_selection_workbench_assets_and_stages_are_served(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "/static/selection-workbench.js" in response.text
    assert "/static/selection-workbench.css" in response.text
    assert 'data-selection-stage="keywords"' in response.text
    assert 'data-selection-stage="direction"' in response.text
    assert 'data-selection-stage="pricing"' in response.text
    assert 'data-selection-stage="report"' in response.text
    assert "Chrome 插件采集商品" not in response.text


def test_selection_project_create_request_is_authenticated_and_errors_are_visible(client):
    page = client.get("/").text
    script = client.get("/static/selection-workbench.js").text

    assert 'Authorization: `Bearer ${token}`' in script
    assert '/static/selection-workbench.js?v=selection-mcp-full-20260715-2' in page
    assert page.index('id="selection-notice"') < page.index('id="selection-project-workspace"')


def test_frontend_dashboard_contains_listing_optimization_entry():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "page-listing-optimization" in response.text
    assert "Listing" in response.text
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


def test_listing_optimization_endpoint_uses_configured_llm(monkeypatch):
    class FakeLLM:
        def __init__(self) -> None:
            self.prompts = []

        def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.prompts.append((system_prompt, user_prompt))
            return (
                "Title: Rechargeable Portable Fan for Travel\n"
                "Bullet Points:\n"
                "- Three speed airflow for desk and travel use\n"
                "- USB rechargeable battery for cordless convenience\n"
                "- Quiet motor for work and bedroom use\n"
                "- Compact handheld design for bags and commutes\n"
                "- Easy controls for everyday cooling\n"
                "Description: A compact rechargeable fan for personal cooling.\n"
                "Search Terms: portable fan handheld fan rechargeable fan"
            )

    llm = FakeLLM()
    monkeypatch.setattr("app.main.build_llm_client", lambda env: llm)
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
    assert payload["generated_by_ai"] is True
    assert payload["listing"]["title"] == "Rechargeable Portable Fan for Travel"
    assert len(payload["listing"]["bullets"]) == 5
    assert payload["quality_score"]["overall_score"] > 0
    assert len(payload["quality_score"]["dimensions"]) == 8
    assert payload["keyword_coverage"]["items"]
    assert "Portable handheld fan" in llm.prompts[0][1]
    assert "usb rechargeable fan" in llm.prompts[0][1]


def test_listing_optimization_endpoint_rejects_empty_description():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/listing/optimize",
        json={"product_description": " ", "keywords": "portable fan", "marketplace": "US"},
    )

    assert response.status_code == 400


def test_legacy_selection_and_chrome_routes_are_removed():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    assert client.post("/api/selection/research", json={"keyword": "fan"}).status_code == 404
    assert client.get("/api/chrome/products").status_code == 404
    assert client.post("/api/chrome/analyze", json={"asins": []}).status_code == 404


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

    seed_operational_data(
        sku_rows=[
            {
                "sku": "SKU-001",
                "target_acos": 0.3,
                "safety_stock_days": 30,
                "lifecycle": "stable",
                "replenishment_days": 25,
            }
        ],
        sales_rows=[
            {"sku": "SKU-001", "date": f"2026-01-{day:02d}", "units_sold": 11 - day, "sales_amount": 100}
            for day in range(1, 8)
        ],
        ads_rows=[
            {
                "sku": "SKU-001",
                "date": "2026-01-07",
                "impressions": 1000,
                "clicks": 30,
                "spend": 45,
                "ad_orders": 0,
                "ad_sales": 100,
            }
        ],
        inventory_rows=[
            {
                "sku": "SKU-001",
                "date": "2026-01-07",
                "available_inventory": 40,
                "inbound_inventory": 0,
                "reserved_inventory": 0,
            }
        ],
    )

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

    # SKU-001 前 7 天销量 100，第 8 天销量 10（触发 sales_drop）
    seed_operational_data(
        sku_rows=[{"sku": "SKU-001"}],
        sales_rows=[
            {"sku": "SKU-001", "date": f"2026-01-{day:02d}", "units_sold": 100, "sales_amount": 2999}
            for day in range(1, 8)
        ]
        + [{"sku": "SKU-001", "date": "2026-01-08", "units_sold": 10, "sales_amount": 299.9}],
        ads_rows=[
            {"sku": "SKU-001", "date": "2026-01-08", "impressions": 1000, "clicks": 30, "spend": 45, "ad_orders": 5, "ad_sales": 150}
        ],
        inventory_rows=[
            {"sku": "SKU-001", "date": "2026-01-08", "available_inventory": 100, "inbound_inventory": 0, "reserved_inventory": 0}
        ],
    )

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

    seed_operational_data(
        sku_rows=[{"sku": "SKU-001"}],
        sales_rows=[{"sku": "SKU-001", "date": "2026-01-07", "units_sold": 50, "sales_amount": 999.5}],
    )

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


# ==================== 自动化任务 ====================


def test_automation_tasks_list_returns_data():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/api/automation/tasks")

    assert response.status_code == 200
    tasks = response.json()
    assert isinstance(tasks, list)
    assert len(tasks) >= 1
    task = tasks[0]
    assert "task_id" in task
    assert "name" in task
    assert "task_type" in task
    assert "schedule_time" in task
    assert "enabled" in task
    assert "status" in task


def test_automation_task_enable_disable():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    tasks = client.get("/api/automation/tasks").json()
    task_id = tasks[0]["task_id"]

    # 禁用
    resp = client.post(f"/api/automation/tasks/{task_id}/disable")
    assert resp.status_code == 200
    detail = client.get(f"/api/automation/tasks/{task_id}").json()
    assert detail["enabled"] is False

    # 启用
    resp = client.post(f"/api/automation/tasks/{task_id}/enable")
    assert resp.status_code == 200
    detail = client.get(f"/api/automation/tasks/{task_id}").json()
    assert detail["enabled"] is True


def test_automation_task_run():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    tasks = client.get("/api/automation/tasks").json()
    task_id = tasks[0]["task_id"]

    resp = client.post(f"/api/automation/tasks/{task_id}/run")
    assert resp.status_code == 200
    result = resp.json()
    assert "success" in result


def test_automation_task_update_schedule():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    tasks = client.get("/api/automation/tasks").json()
    task_id = tasks[0]["task_id"]

    resp = client.patch(
        f"/api/automation/tasks/{task_id}",
        json={"schedule_time": "10:30"},
    )
    assert resp.status_code == 200
    detail = client.get(f"/api/automation/tasks/{task_id}").json()
    assert detail["schedule_time"] == "10:30"


def test_automation_page_html_present():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.get("/")
    assert "page-automation" in response.text
    assert "tasks-grid" in response.text
    assert "refresh-tasks" in response.text
