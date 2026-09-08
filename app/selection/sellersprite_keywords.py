"""卖家精灵关键词调研的直接 MCP 调用。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.selection.adapters import SellerSpriteAdapter
from app.selection.contracts import McpCallResult, McpCapability


KEYWORD_PAGE_SIZE = 20
MAX_KEYWORD_PAGES = 5


class SellerSpriteKeywordCollector:
    """按卖家精灵 MCP 的真实 Schema 收集关键词，不使用旧能力映射。"""

    def __init__(self, client: Any, source_id: str = "seller-sprite", source_name: str = "卖家精灵") -> None:
        self.client = client
        self.source_id = source_id
        self.source_name = source_name

    async def collect(self, input_type: str, input_value: str, marketplace: str) -> McpCallResult:
        if input_type == "asin":
            return await self._collect_pages(
                McpCapability.ASIN_KEYWORD_REVERSE,
                "traffic_extend",
                {"asinList": [input_value], "marketplace": marketplace, "queryType": 2},
            )
        if input_type == "seed":
            return await self._collect_pages(
                McpCapability.KEYWORD_EXPAND,
                "keyword_miner",
                {"keyword": input_value, "marketplace": marketplace},
            )
        return await self._collect_category(input_value, marketplace)

    async def _collect_category(self, category: str, marketplace: str) -> McpCallResult:
        node_raw = await self.client.call_tool(
            "product_node", {"request": {"keyword": category, "marketplace": marketplace}}
        )
        node_payload = _payload(node_raw)
        node = _first_node(node_payload)
        if not node:
            return _failure(self.source_id, self.source_name, McpCapability.CATEGORY_KEYWORDS, "product_node", "未找到匹配的类目节点", [node_raw])
        node_id = node.get("nodeIdPath") or node.get("node_id_path")
        if not isinstance(node_id, str) or not node_id:
            return _failure(self.source_id, self.source_name, McpCapability.CATEGORY_KEYWORDS, "product_node", "类目节点响应缺少 nodeIdPath", [node_raw])
        result = await self._collect_pages(
            McpCapability.CATEGORY_KEYWORDS,
            "keyword_research",
            {"departments": [node_id], "marketplace": marketplace},
        )
        result.raw_data["node"] = node_raw
        return result

    async def _collect_pages(
        self, capability: McpCapability, tool_name: str, request: dict[str, Any]
    ) -> McpCallResult:
        pages: list[Any] = []
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        page = 1
        last_page = 1
        while page <= last_page and page <= MAX_KEYWORD_PAGES:
            raw = await self.client.call_tool(
                tool_name,
                {"request": {**request, "page": page, "size": KEYWORD_PAGE_SIZE}},
            )
            pages.append(raw)
            error = _mcp_error(raw)
            if error:
                return _failure(self.source_id, self.source_name, capability, tool_name, error, pages)
            payload = _payload(raw)
            data = payload.get("data", {}) if isinstance(payload, dict) else {}
            if not isinstance(data, dict):
                return _failure(self.source_id, self.source_name, capability, tool_name, "MCP 响应缺少 data 对象", pages)
            last_page = min(MAX_KEYWORD_PAGES, max(last_page, int(data.get("pages") or 1)))
            for item in data.get("items") or []:
                if not isinstance(item, dict):
                    continue
                keyword = item.get("keyword")
                key = str(keyword).casefold() if keyword else json.dumps(item, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    records.append(item)
            page += 1

        normalized = SellerSpriteAdapter(self.source_id, self.source_name).normalize(
            capability, tool_name, {"data": records}
        )
        normalized.raw_data = {"pages": pages}
        return normalized


def _payload(raw: Any) -> Any:
    if isinstance(raw, dict) and isinstance(raw.get("content"), list):
        for block in raw["content"]:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                try:
                    return json.loads(block["text"])
                except json.JSONDecodeError:
                    return raw
    return raw


def _mcp_error(raw: Any) -> str:
    if isinstance(raw, dict) and raw.get("isError"):
        payload = _payload(raw)
        return str(payload.get("message") if isinstance(payload, dict) else payload)
    payload = _payload(raw)
    if isinstance(payload, dict) and payload.get("code") not in (None, "OK"):
        return str(payload.get("message") or payload.get("code"))
    return ""


def _first_node(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        for key in ("data", "items", "list", "records"):
            found = _first_node(payload.get(key))
            if found:
                return found
        if "nodeIdPath" in payload or "node_id_path" in payload:
            return payload
    if isinstance(payload, list):
        for item in payload:
            found = _first_node(item)
            if found:
                return found
    return None


def _failure(source_id: str, source_name: str, capability: McpCapability, tool_name: str, warning: str, pages: list[Any]) -> McpCallResult:
    return McpCallResult(source_id, source_name, capability, tool_name, datetime.now(UTC), "failed", [], [], [warning], {"pages": pages})
