"""将领星 MCP 的真实返回转换为运营模块统一数据合同。"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from app.agents.mcp_tools import StreamableHttpMCPClient
from app.db.models import McpDataSource
from app.selection.contracts import McpCapability
from app.selection.credentials import EnvCredentialStore


OPERATIONS_CAPABILITIES = (
    McpCapability.SALES_SUMMARY,
    McpCapability.SALES_TREND,
    McpCapability.AD_PERFORMANCE,
    McpCapability.AD_ENTITIES,
    McpCapability.INVENTORY_SNAPSHOT,
    McpCapability.REPLENISHMENT_DATA,
)

CAPABILITY_FIELDS: dict[McpCapability, tuple[str, ...]] = {
    McpCapability.SALES_SUMMARY: (
        "sales_amount", "units_sold", "order_count", "refund_amount", "gross_profit",
    ),
    McpCapability.SALES_TREND: (
        "date", "store", "marketplace", "asin", "sku", "sales_amount", "units_sold",
        "order_count", "refund_amount", "gross_profit",
    ),
    McpCapability.AD_PERFORMANCE: (
        "impressions", "clicks", "spend", "ad_orders", "ad_sales", "ctr", "cpc",
        "cvr", "acos", "roas", "tacos",
    ),
    McpCapability.AD_ENTITIES: (
        "level", "entity_id", "entity_name", "campaign_name", "ad_group_name",
        "target", "search_term", "match_type", "budget", "bid", "impressions",
        "clicks", "spend", "ad_orders", "ad_sales", "acos", "roas",
    ),
    McpCapability.INVENTORY_SNAPSHOT: (
        "store", "marketplace", "warehouse", "asin", "sku", "available_inventory",
        "reserved_inventory", "inbound_inventory", "transfer_inventory",
        "unsellable_inventory", "inventory_age_days", "inventory_value",
    ),
    McpCapability.REPLENISHMENT_DATA: (
        "sku", "daily_sales", "available_days", "coverage_days", "lead_time_days",
        "expected_stockout_date", "recommended_replenishment", "expected_arrival_date",
        "purchase_order_status",
    ),
}


class LingxingMcpProvider:
    """按显式能力映射调用领星 MCP；未配置时返回可识别状态。"""

    def __init__(self, *, client_factory=None) -> None:
        self.client_factory = client_factory or self._build_client

    def describe(self, session) -> dict[str, Any]:
        sources = self._sources(session)
        configured: dict[str, dict[str, Any]] = {}
        for capability in OPERATIONS_CAPABILITIES:
            source = self._source_for(sources, capability)
            mapping = self._mapping(source, capability) if source else None
            tool_configured = bool(mapping and self._tool_name(mapping))
            fields_configured = bool(
                mapping and isinstance(mapping.get("field_mapping"), dict) and mapping["field_mapping"]
            )
            configured[capability.value] = {
                "configured": tool_configured and fields_configured,
                "tool_configured": tool_configured,
                "field_mapping_configured": fields_configured,
                "source_name": source.name if source else None,
                "required_fields": list(CAPABILITY_FIELDS[capability]),
            }

        configured_count = sum(item["configured"] for item in configured.values())
        tool_count = sum(item["tool_configured"] for item in configured.values())
        if tool_count == 0:
            status = "not_configured"
            message = "未配置领星 MCP，请在 MCP 对接中配置运营数据能力"
        elif configured_count < len(OPERATIONS_CAPABILITIES):
            status = "partial"
            message = f"已完成 {configured_count}/{len(OPERATIONS_CAPABILITIES)} 项领星能力映射"
        else:
            status = "configured"
            message = "领星 MCP 运营数据能力已配置"
        return {
            "provider": "lingxing",
            "status": status,
            "configured": tool_count > 0,
            "message": message,
            "capabilities": configured,
            "source_updated_at": None,
        }

    async def call(
        self,
        session,
        capability: McpCapability,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        source = self._source_for(self._sources(session), capability)
        mapping = self._mapping(source, capability) if source else None
        tool_name = self._tool_name(mapping)
        if source is None or not tool_name:
            return self._failure(capability, "not_configured", "未配置该领星 MCP 能力")

        field_mapping = mapping.get("field_mapping", {}) if isinstance(mapping, dict) else {}
        if not isinstance(field_mapping, dict) or not field_mapping:
            return self._failure(capability, "mapping_required", "已配置工具，但未配置字段映射")

        try:
            raw_data = await self.client_factory(source).call_tool(
                tool_name,
                self._map_arguments(mapping, arguments),
            )
            raw_records = _extract_records(_decode_payload(raw_data))
            records = [_normalize_record(record, field_mapping) for record in raw_records]
        except Exception:
            return self._failure(capability, "failed", "领星 MCP 调用失败")

        collected_at = datetime.now(UTC).isoformat()
        return {
            "capability": capability.value,
            "status": "succeeded",
            "source_name": source.name,
            "source_updated_at": collected_at,
            "records": records,
            "warnings": [],
        }

    @staticmethod
    def _sources(session) -> list[McpDataSource]:
        return list(
            session.query(McpDataSource)
            .filter(McpDataSource.enabled.is_(True))
            .order_by(McpDataSource.priority, McpDataSource.id)
            .all()
        )

    @staticmethod
    def _source_for(
        sources: list[McpDataSource], capability: McpCapability
    ) -> McpDataSource | None:
        return next(
            (source for source in sources if capability.value in (source.capability_config_json or {})),
            None,
        )

    @staticmethod
    def _mapping(source: McpDataSource | None, capability: McpCapability) -> dict | None:
        if source is None or not isinstance(source.capability_config_json, dict):
            return None
        mapping = source.capability_config_json.get(capability.value)
        return mapping if isinstance(mapping, dict) else None

    @staticmethod
    def _tool_name(mapping: dict | None) -> str:
        return str((mapping or {}).get("tool", "")).strip()

    @staticmethod
    def _map_arguments(mapping: dict, arguments: dict[str, Any]) -> dict[str, Any]:
        argument_map = mapping.get("argument_map")
        if not isinstance(argument_map, dict) or not argument_map:
            return arguments
        return {
            str(target): arguments[source]
            for source, target in argument_map.items()
            if source in arguments and arguments[source] is not None
        }

    @staticmethod
    def _failure(capability: McpCapability, status: str, warning: str) -> dict[str, Any]:
        return {
            "capability": capability.value,
            "status": status,
            "source_name": None,
            "source_updated_at": None,
            "records": [],
            "warnings": [warning],
        }

    @staticmethod
    def _build_client(source: McpDataSource) -> StreamableHttpMCPClient:
        store = EnvCredentialStore(os.environ, lambda _updates: None)
        headers = store.load_headers(source.credential_reference or "")
        return StreamableHttpMCPClient(url=source.url, headers=headers)


def _decode_payload(raw_data: Any) -> Any:
    if not isinstance(raw_data, dict) or not isinstance(raw_data.get("content"), list):
        return raw_data
    for block in raw_data["content"]:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        text = block.get("text")
        if not isinstance(text, str):
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("领星 MCP 文本响应不是合法 JSON") from exc
    return raw_data


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("records", "items", "list", "data", "result"):
        if key in payload:
            records = _extract_records(payload[key])
            if records or payload[key] == []:
                return records
    return [payload]


def _normalize_record(record: dict[str, Any], field_mapping: dict[str, str]) -> dict[str, Any]:
    return {
        canonical: _read_path(record, str(source_path))
        for canonical, source_path in field_mapping.items()
    }


def _read_path(record: dict[str, Any], path: str) -> Any:
    value: Any = record
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value
