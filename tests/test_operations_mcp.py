from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.models import McpDataSource
from app.deps import get_session
from app.integrations.lingxing.provider import LingxingMcpProvider
from app.routes.operations import router
from app.selection.contracts import McpCapability


class FakeClient:
    async def call_tool(self, tool_name: str, arguments: dict):
        assert tool_name == "sales_report"
        assert arguments == {"range": 30}
        return {
            "content": [
                {
                    "type": "text",
                    "text": '{"data":[{"totalSales":123.45,"units":8}]}',
                }
            ]
        }


def test_operations_dashboards_report_not_configured(session_factory):
    app = FastAPI()
    app.include_router(router)

    def override_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        status = client.get("/api/operations/source-status")
        sales = client.get("/api/sales-monitor/dashboard")
        ads = client.get("/api/ads-analysis/dashboard")
        inventory = client.get("/api/inventory-agent/dashboard")

    assert status.status_code == 200
    assert status.json()["status"] == "not_configured"
    assert sales.json()["summary"]["records"] == []
    assert ads.json()["performance"]["status"] == "not_configured"
    assert inventory.json()["snapshot"]["status"] == "not_configured"


def test_lingxing_provider_maps_configured_fields(session):
    source = McpDataSource(
        name="领星",
        url="https://example.com/mcp",
        transport="streamable_http",
        enabled=True,
        priority=1,
        capability_config_json={
            "sales_summary": {
                "tool": "sales_report",
                "argument_map": {"days": "range"},
                "field_mapping": {
                    "sales_amount": "totalSales",
                    "units_sold": "units",
                },
            }
        },
    )
    session.add(source)
    session.commit()

    provider = LingxingMcpProvider(client_factory=lambda _source: FakeClient())
    result = asyncio.run(
        provider.call(session, McpCapability.SALES_SUMMARY, {"days": 30})
    )

    assert result["status"] == "succeeded"
    assert result["records"] == [{"sales_amount": 123.45, "units_sold": 8}]
    assert provider.describe(session)["status"] == "partial"
