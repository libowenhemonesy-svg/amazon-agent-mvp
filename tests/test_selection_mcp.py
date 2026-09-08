import asyncio
from datetime import datetime

import pytest

from app.agents.mcp_tools import build_legacy_mcp_data_source
from app.selection import adapters as mcp_adapter
from app.selection.adapters import SellerSpriteAdapter
from app.selection.contracts import McpCallResult, McpCapability
from app.selection import mcp_registry
from app.selection.mcp_registry import McpRegistry
from app.selection.sellersprite_keywords import SellerSpriteKeywordCollector


class FakeMcpClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.error:
            raise self.error
        return self.response


class SequencedMcpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self.responses.pop(0)


def _mcp_page(page, pages, items):
    import json

    return {
        "content": [{"type": "text", "text": json.dumps({
            "code": "OK", "data": {"page": page, "pages": pages, "items": items}
        })}]
    }


def test_sellersprite_collector_uses_page_size_and_limits_to_five_pages():
    client = SequencedMcpClient([
        _mcp_page(page, 8, [{"keyword": f"dog bowl {page}", "searches": page}])
        for page in range(1, 9)
    ])

    result = asyncio.run(
        SellerSpriteKeywordCollector(client).collect("asin", "B0G49YLYSK", "US")
    )

    assert [name for name, _ in client.calls] == ["traffic_extend"] * 5
    assert client.calls[0][1] == {
        "request": {
            "asinList": ["B0G49YLYSK"], "marketplace": "US", "queryType": 2,
            "page": 1, "size": 20,
        }
    }
    assert [call[1]["request"]["page"] for call in client.calls] == [1, 2, 3, 4, 5]
    assert all(call[1]["request"]["size"] == 20 for call in client.calls)
    assert len(result.records) == 5
    assert len(result.raw_data["pages"]) == 5


def test_capability_contract_has_eight_approved_values():
    assert {capability.value for capability in McpCapability} == {
        "keyword_expand",
        "asin_keyword_reverse",
        "category_keywords",
        "keyword_metrics",
        "keyword_trend",
        "competitor_search",
        "competitor_metrics",
        "exchange_rate",
    }


def test_keyword_adapter_keeps_records_raw_data_and_lineage():
    raw = {
        "data": [
            {
                "keyword": "portable fan",
                "searchVolume": 42000,
                "unknownMetric": 99,
            }
        ]
    }
    adapter = SellerSpriteAdapter(source_id="seller", source_name="卖家精灵")

    result = adapter.normalize(McpCapability.KEYWORD_EXPAND, "keyword_research", raw)

    assert isinstance(result, McpCallResult)
    assert result.records[0]["keyword"] == "portable fan"
    assert result.records[0]["search_volume"] == 42000
    assert result.records[0]["product_count"] is None
    assert "unknown_metric" not in result.records[0]
    assert result.field_lineage[0]["search_volume"]["raw_path"] == "data[0].searchVolume"
    assert result.raw_data is raw
    assert result.status == "succeeded"
    assert isinstance(result.collected_at, datetime)


def test_keyword_adapter_normalizes_expand_keywords_metrics_and_competitors():
    raw = {
        "data": [
            {
                "keyword": "dog bowls",
                "keywordTranslation": "狗碗",
                "acRecommended": "相关",
                "trafficShare": 0.29,
                "trafficType": "视频广告词/SP广告词",
                "monthlySearchVolume": 188462,
                "monthlyPurchaseVolume": 6822,
                "purchaseRate": 0.0362,
                "spr": 156,
                "adCompetitorCount": 268,
                "ppcBid": "$0.98",
                "top1Asin": "B09CGX6WY6",
                "top1ClickShare": 0.0915,
                "topTenAsins": "B0GDYMV2DW,B09CGX6WY6",
            }
        ]
    }

    result = SellerSpriteAdapter("seller", "卖家精灵").normalize(
        McpCapability.KEYWORD_EXPAND, "keyword_research", raw
    )

    assert result.records[0]["keyword_translation"] == "狗碗"
    assert result.records[0]["monthly_search_volume"] == 188462
    assert result.records[0]["ppc_bid"] == "$0.98"
    assert result.records[0]["top_1_asin"] == "B09CGX6WY6"
    assert result.field_lineage[0]["top_ten_asins"]["raw_path"] == "data[0].topTenAsins"


def test_adapter_reads_json_from_mcp_text_content():
    raw = {
        "content": [
            {
                "type": "text",
                "text": '{"data":[{"keyword":"portable fan","searchVolume":42000}]}',
            }
        ]
    }

    result = SellerSpriteAdapter("seller", "卖家精灵").normalize(
        McpCapability.KEYWORD_EXPAND,
        "keyword_research",
        raw,
    )

    assert result.records[0]["search_volume"] == 42000
    assert (
        result.field_lineage[0]["search_volume"]["raw_path"]
        == "content[0].text.data[0].searchVolume"
    )
    assert result.raw_data is raw


def test_adapter_reads_nested_result_array():
    raw = {"result": {"data": {"items": [{"keyword": "desk fan", "products": 321}]}}}

    result = SellerSpriteAdapter("seller", "卖家精灵").normalize(
        McpCapability.KEYWORD_METRICS,
        "keyword_metrics",
        raw,
    )

    assert result.records[0]["keyword"] == "desk fan"
    assert result.records[0]["product_count"] == 321
    assert result.field_lineage[0]["product_count"]["raw_path"] == (
        "result.data.items[0].products"
    )


def test_adapter_keeps_missing_standard_fields_as_none():
    raw = {"data": [{"keyword": "quiet fan"}]}

    result = SellerSpriteAdapter("seller", "卖家精灵").normalize(
        McpCapability.KEYWORD_EXPAND,
        "keyword_research",
        raw,
    )

    assert result.records[0]["keyword"] == "quiet fan"
    assert set(result.records[0]) == set(mcp_adapter._KEYWORD_FIELDS)
    assert all(
        value is None
        for field, value in result.records[0].items()
        if field != "keyword"
    )
    assert "search_volume" not in result.field_lineage[0]


def test_invalid_json_text_is_an_explicit_failure_without_records():
    raw = {"content": [{"type": "text", "text": "{not-json"}]}

    result = SellerSpriteAdapter("seller", "卖家精灵").normalize(
        McpCapability.KEYWORD_EXPAND,
        "keyword_research",
        raw,
    )

    assert result.status == "failed"
    assert result.records == []
    assert result.field_lineage == []
    assert result.raw_data is raw
    assert "JSON" in result.warnings[0]


def test_registry_calls_only_explicitly_configured_tool_and_maps_arguments():
    source = {
        "id": "seller",
        "name": "卖家精灵",
        "url": "https://mcp.example/mcp",
        "transport": "streamable_http",
        "enabled": True,
        "priority": 5,
        "capability_config_json": {
            "keyword_expand": {
                "tool": "keyword_research",
                "argument_map": {"keyword": "seed", "marketplace": "market"},
            }
        },
    }
    client = FakeMcpClient({"data": [{"keyword": "portable fan"}]})
    registry = McpRegistry([source], client_factory=lambda _source: client)

    results = asyncio.run(
        registry.call(
            McpCapability.KEYWORD_EXPAND,
            {"keyword": "fan", "marketplace": "US", "ignored": "value"},
        )
    )

    assert client.calls == [("keyword_research", {"seed": "fan", "market": "US"})]
    assert results[0].status == "succeeded"
    assert results[0].tool_name == "keyword_research"


def test_registry_returns_not_supported_without_explicit_mapping():
    source = {
        "id": "seller",
        "name": "卖家精灵",
        "enabled": True,
        "priority": 5,
        "capability_config_json": {},
    }
    client = FakeMcpClient({"data": [{"keyword": "不应调用"}]})
    registry = McpRegistry([source], client_factory=lambda _source: client)

    results = asyncio.run(registry.call(McpCapability.KEYWORD_EXPAND, {"keyword": "fan"}))

    assert client.calls == []
    assert results[0].status == "failed"
    assert results[0].records == []
    assert "不支持能力" in results[0].warnings[0]


def test_collect_keywords_constructs_streamable_client_with_keyword_arguments(monkeypatch):
    client = SequencedMcpClient([
        _mcp_page(1, 1, [{"keyword": "dog bowls", "searches": 10}]),
    ])
    created = {}

    def fake_streamable_client(*, url, headers):
        created["url"] = url
        created["headers"] = headers
        return client

    monkeypatch.setenv("SELLERSPRITE_MCP_URL", "https://seller.example/mcp")
    monkeypatch.setenv("SELLERSPRITE_API_KEY", "secret-value")
    monkeypatch.setattr(mcp_registry, "StreamableHttpMCPClient", fake_streamable_client)

    results = asyncio.run(McpRegistry().collect_keywords("asin", "B0G49YLYSK", "US"))

    assert created["url"] == "https://seller.example/mcp"
    assert "secret-key" in created["headers"]
    assert results[0].status == "succeeded"
    assert results[0].records[0]["keyword"] == "dog bowls"


def test_registry_reports_source_timeout_without_fabricated_records():
    source = {
        "id": "seller",
        "name": "卖家精灵",
        "enabled": True,
        "priority": 5,
        "capability_config_json": {"keyword_expand": {"tool": "keyword_research"}},
    }
    client = FakeMcpClient(error=TimeoutError("secret endpoint detail"))
    registry = McpRegistry([source], client_factory=lambda _source: client)

    results = asyncio.run(registry.call(McpCapability.KEYWORD_EXPAND, {"keyword": "fan"}))

    assert results[0].status == "failed"
    assert results[0].records == []
    assert results[0].raw_data is None
    assert results[0].warnings == ["数据源调用超时"]


def test_legacy_environment_materializes_source_without_guessing_capabilities():
    source = build_legacy_mcp_data_source(
        {
            "MCP_SERVER_URL": "https://mcp.example/mcp",
            "MCP_SERVER_TRANSPORT": "streamable_http",
            "MCP_SERVER_CAPABILITY_CONFIG": (
                '{"keyword_expand":{"tool":"keyword_research"}}'
            ),
        }
    )

    assert source is not None
    assert source["name"] == "卖家精灵"
    assert source["capability_config_json"] == {
        "keyword_expand": {"tool": "keyword_research"}
    }
    assert "MCP_SERVER_URL" not in source
    assert build_legacy_mcp_data_source({}) is None


def test_legacy_environment_uses_stable_domain_source_id_in_standard_result():
    source = build_legacy_mcp_data_source(
        {
            "SELLERSPRITE_MCP_URL": "https://mcp.example/mcp",
            "SELLERSPRITE_MCP_CAPABILITY_CONFIG": (
                '{"keyword_expand":{"tool":"keyword_research"}}'
            ),
        }
    )
    client = FakeMcpClient({"data": [{"keyword": "portable fan"}]})
    registry = McpRegistry([source], client_factory=lambda _source: client)

    results = asyncio.run(registry.call(McpCapability.KEYWORD_EXPAND, {"keyword": "fan"}))

    assert results[0].source_id == "seller-sprite"
    assert "legacy" not in results[0].source_id
    assert "sellersprite_mcp" not in results[0].source_id


def test_registry_rejects_legacy_sse_without_sending_request(monkeypatch):
    source = {
        "id": "legacy-sse",
        "name": "旧 SSE 数据源",
        "url": "https://mcp.example/mcp",
        "transport": "sse",
        "enabled": True,
        "capability_config_json": {"keyword_expand": {"tool": "keyword_research"}},
    }
    client_created = False

    def fail_if_client_created(**_kwargs):
        nonlocal client_created
        client_created = True
        raise AssertionError("不应创建 Streamable HTTP 客户端")

    monkeypatch.setattr(mcp_registry, "StreamableHttpMCPClient", fail_if_client_created)

    results = asyncio.run(
        McpRegistry([source]).call(McpCapability.KEYWORD_EXPAND, {"keyword": "fan"})
    )

    assert client_created is False
    assert results[0].status == "failed"
    assert results[0].warnings == ["不支持的传输方式：sse"]


def test_default_registry_factory_rejects_non_streamable_transport():
    with pytest.raises(ValueError, match="不支持的传输方式：sse"):
        mcp_registry._default_client_factory(
            {"url": "https://mcp.example/mcp", "transport": "sse"}
        )
