from app.integrations.feishu.client import FeishuClient
from app.integrations.feishu.sync import sync_daily_outputs


class FakeTransport:
    def __init__(self):
        self.requests = []

    def post_json(self, url, payload, headers):
        self.requests.append((url, payload, headers))
        return {"code": 0, "data": {"record": {"record_id": "rec001"}}}


class FakeAuthTransport:
    def __init__(self):
        self.requests = []

    def post_json(self, url, payload, headers):
        self.requests.append((url, payload, headers))
        return {"code": 0, "tenant_access_token": "tenant_from_app_credentials"}


def test_feishu_client_upserts_record_with_auth_header():
    transport = FakeTransport()
    client = FeishuClient(
        app_token="base_token",
        table_ids={"alerts": "tbl_alerts"},
        access_token="tenant_token",
        transport=transport,
    )

    result = client.upsert_record(
        table_name="alerts",
        unique_key="2026-01-01:SKU-001:sales_drop",
        fields={"SKU": "SKU-001", "异常类型": "sales_drop"},
    )

    assert result == "rec001"
    url, payload, headers = transport.requests[0]
    assert "tbl_alerts" in url
    assert payload["fields"]["unique_key"] == "2026-01-01:SKU-001:sales_drop"
    assert headers["Authorization"] == "Bearer tenant_token"


def test_feishu_client_can_exchange_app_credentials_for_tenant_token():
    transport = FakeAuthTransport()

    access_token = FeishuClient.get_tenant_access_token(
        app_id="cli_test",
        app_secret="secret_test",
        transport=transport,
    )

    assert access_token == "tenant_from_app_credentials"
    url, payload, headers = transport.requests[0]
    assert url.endswith("/auth/v3/tenant_access_token/internal")
    assert payload == {"app_id": "cli_test", "app_secret": "secret_test"}
    assert headers == {"Content-Type": "application/json; charset=utf-8"}


def test_sync_daily_outputs_upserts_sku_metrics_alerts_and_report_tables():
    transport = FakeTransport()
    client = FeishuClient(
        app_token="base_token",
        table_ids={
            "sku": "tbl_sku",
            "metrics": "tbl_metrics",
            "alerts": "tbl_alerts",
            "reports": "tbl_reports",
        },
        access_token="tenant_token",
        transport=transport,
    )

    result = sync_daily_outputs(
        client=client,
        sku_rows=[
            {
                "sku": "SKU-001",
                "asin": "B0TEST",
                "store": "Store-A",
                "marketplace": "US",
                "product_category": "Kitchen",
                "owner": "运营A",
                "responsible_agent": "Sales-Agent-01",
                "lifecycle": "stable",
                "target_acos": 0.3,
                "target_gross_margin": 0.4,
                "safety_stock_days": 30,
                "enabled": True,
            }
        ],
        metrics=[
            {
                "date": "2026-01-07",
                "sku": "SKU-001",
                "units_sold": 4,
                "sales_amount": 120,
                "acos": 0.45,
                "cvr": 0,
                "inventory_days": 8,
                "gross_margin": 0.35,
                "return_rate": 0.12,
            }
        ],
        alerts=[
            {
                "date": "2026-01-07",
                "sku": "SKU-001",
                "alert_type": "sales_drop",
                "severity": "high",
                "status": "pending",
                "agent_result": {
                    "summary": "销量明显低于短期均值",
                    "recommended_actions": ["检查广告曝光", "检查价格"],
                },
            }
        ],
        report={
            "date": "2026-01-07",
            "summary": "发现 1 个异常",
            "risk_count": 1,
            "pending_count": 1,
        },
    )

    assert result == {"sku": 1, "metrics": 1, "alerts": 1, "reports": 1}
    urls = [request[0] for request in transport.requests]
    assert any("tbl_sku" in url for url in urls)
    assert any("tbl_metrics" in url for url in urls)
    assert any("tbl_alerts" in url for url in urls)
    assert any("tbl_reports" in url for url in urls)
    unique_keys = [request[1]["fields"]["unique_key"] for request in transport.requests]
    assert unique_keys == [
        "SKU-001",
        "2026-01-07:SKU-001",
        "2026-01-07:SKU-001:sales_drop",
        "2026-01-07",
    ]
