"""基于显式能力配置的 MCP 数据源注册表。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from app.agents.mcp_tools import (
    StreamableHttpMCPClient,
    build_legacy_mcp_data_source,
    build_sellersprite_mcp_config,
)
from app.selection.adapters import SellerSpriteAdapter
from app.selection.contracts import McpCallResult, McpCapability
from app.selection.sellersprite_keywords import SellerSpriteKeywordCollector


class McpRegistry:
    """调用所有启用的数据源，且只使用其明确声明的工具。"""

    def __init__(
        self,
        sources: Sequence[Any] | None = None,
        *,
        client_factory: Callable[[Any], Any] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        loaded_sources = list(sources or [])
        if not loaded_sources:
            legacy_source = build_legacy_mcp_data_source(env)
            if legacy_source:
                loaded_sources.append(legacy_source)
        self.sources = loaded_sources
        self.client_factory = client_factory or _default_client_factory

    async def call(
        self,
        capability: McpCapability,
        arguments: dict[str, Any],
    ) -> list[McpCallResult]:
        enabled = [source for source in self.sources if _source_value(source, "enabled", True)]
        enabled.sort(key=lambda source: _source_value(source, "priority", 10))
        return [await self._call_source(source, capability, arguments) for source in enabled]

    async def collect_keywords(
        self, input_type: str, input_value: str, marketplace: str
    ) -> list[McpCallResult]:
        """直接调用卖家精灵关键词工具，不使用旧能力映射。"""
        config = build_sellersprite_mcp_config()
        if not config:
            return [
                _failure_result(
                    "seller-sprite",
                    "卖家精灵",
                    McpCapability.KEYWORD_EXPAND,
                    "",
                    "未配置卖家精灵 MCP",
                )
            ]
        server = config["sellersprite"]
        result = await SellerSpriteKeywordCollector(
            StreamableHttpMCPClient(
                url=server["url"],
                headers=server.get("headers", {}),
            )
        ).collect(input_type, input_value, marketplace)
        return [result]

    async def _call_source(
        self,
        source: Any,
        capability: McpCapability,
        arguments: dict[str, Any],
    ) -> McpCallResult:
        source_id = str(_source_value(source, "id", ""))
        source_name = str(_source_value(source, "name", ""))
        transport = str(_source_value(source, "transport", "streamable_http"))
        if transport != "streamable_http":
            return _failure_result(
                source_id,
                source_name,
                capability,
                "",
                f"不支持的传输方式：{transport}",
            )
        config = _source_value(source, "capability_config_json", {}) or {}
        mapping = config.get(capability.value) if isinstance(config, dict) else None
        tool_name = _configured_tool_name(mapping)
        if not tool_name:
            return _failure_result(
                source_id,
                source_name,
                capability,
                "",
                "数据源不支持能力：未配置明确工具映射",
            )

        mapped_arguments = _map_arguments(mapping, arguments)
        timeout = _configured_timeout(mapping, source)
        try:
            client = self.client_factory(source)
            call = client.call_tool(tool_name, mapped_arguments)
            raw_data = await asyncio.wait_for(call, timeout=timeout) if timeout else await call
        except (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException):
            return _failure_result(
                source_id, source_name, capability, tool_name, "数据源调用超时"
            )
        except Exception:
            return _failure_result(
                source_id, source_name, capability, tool_name, "数据源调用失败"
            )

        return SellerSpriteAdapter(source_id, source_name).normalize(
            capability, tool_name, raw_data
        )


def _source_value(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _configured_tool_name(mapping: Any) -> str:
    if isinstance(mapping, str):
        return mapping.strip()
    if not isinstance(mapping, dict):
        return ""
    return str(mapping.get("tool") or mapping.get("tool_name") or "").strip()


def _map_arguments(mapping: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(mapping, dict) or "argument_map" not in mapping:
        return dict(arguments)
    argument_map = mapping.get("argument_map")
    if not isinstance(argument_map, dict):
        return {}
    return {
        str(target_name): arguments[source_name]
        for source_name, target_name in argument_map.items()
        if source_name in arguments
    }


def _configured_timeout(mapping: Any, source: Any) -> float | None:
    value = mapping.get("timeout") if isinstance(mapping, dict) else None
    if value is None:
        value = _source_value(source, "timeout", None)
    if value is None:
        return None
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return None
    return timeout if timeout > 0 else None


def _failure_result(
    source_id: str,
    source_name: str,
    capability: McpCapability,
    tool_name: str,
    warning: str,
) -> McpCallResult:
    return McpCallResult(
        source_id=source_id,
        source_name=source_name,
        capability=capability,
        tool_name=tool_name,
        collected_at=datetime.now(UTC),
        status="failed",
        records=[],
        field_lineage=[],
        warnings=[warning],
        raw_data=None,
    )


def _default_client_factory(source: Any) -> StreamableHttpMCPClient:
    transport = str(_source_value(source, "transport", "streamable_http"))
    if transport != "streamable_http":
        raise ValueError(f"不支持的传输方式：{transport}")
    return StreamableHttpMCPClient(
        url=str(_source_value(source, "url", "")),
        headers=_source_value(source, "headers", {}) or {},
    )
