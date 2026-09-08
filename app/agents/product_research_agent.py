from __future__ import annotations

from typing import Any


class ProductResearchAgent:
    """选品研究 Agent：只通过已配置 MCP 数据源读取真实市场数据。"""

    def __init__(self, *, mcp_research_service, llm_client=None) -> None:
        self.mcp_research_service = mcp_research_service
        self.llm_client = llm_client

    async def run(self, state: dict) -> dict:
        entities = state.get("entities", {})
        keyword = (entities.get("keyword") or state.get("user_message") or "").strip()
        marketplace = (entities.get("marketplace") or "US").upper()
        category = entities.get("category") or "all"
        try:
            result = await self.mcp_research_service.research(
                keyword=keyword,
                marketplace=marketplace,
                category=category,
            )
        except Exception:
            return {
                "agent_name": "ProductResearchAgent",
                "keyword": keyword,
                "summary": "MCP 数据调用失败，请检查数据源连接和配置。",
                "evidence": [],
                "actions": [],
                "raw": {},
            }

        return {
            "agent_name": "ProductResearchAgent",
            "keyword": keyword,
            "summary": _format_mcp_summary(result),
            "evidence": [],
            "actions": [],
            "raw": result,
        }


def _format_mcp_summary(result: dict[str, Any]) -> str:
    source_names = _source_names(result)
    lines = [
        f"【数据来源：{'、'.join(source_names)}】",
        (
            f"关键词：{result.get('keyword', '')} "
            f"站点：{result.get('marketplace', '')} "
            f"类目：{result.get('category', 'all')}"
        ),
    ]
    summary = str(result.get("summary") or "").strip()
    if summary:
        lines.extend(["", summary])
    snapshot_ids = result.get("raw_snapshot_ids") or result.get("snapshot_ids") or []
    if snapshot_ids:
        lines.extend(["", f"原始快照：{'、'.join(str(item) for item in snapshot_ids)}"])
    lines.extend(["", "【MCP 原始数据】", str(result.get("raw_data", {}))])
    return "\n".join(lines)


def _source_names(result: dict[str, Any]) -> list[str]:
    names: list[str] = []
    direct = result.get("source_name")
    if isinstance(direct, str) and direct.strip():
        names.append(direct.strip())
    for source in result.get("sources") or []:
        if isinstance(source, dict):
            name = source.get("source_name") or source.get("name")
        else:
            name = source
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return list(dict.fromkeys(names)) or ["MCP 数据源"]
