"""选品 MCP 数据源的统一领域合同。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class McpCapability(StrEnum):
    """平台支持的 MCP 能力。"""

    KEYWORD_EXPAND = "keyword_expand"
    ASIN_KEYWORD_REVERSE = "asin_keyword_reverse"
    CATEGORY_KEYWORDS = "category_keywords"
    KEYWORD_METRICS = "keyword_metrics"
    KEYWORD_TREND = "keyword_trend"
    COMPETITOR_SEARCH = "competitor_search"
    COMPETITOR_METRICS = "competitor_metrics"
    EXCHANGE_RATE = "exchange_rate"
    SALES_SUMMARY = "sales_summary"
    SALES_TREND = "sales_trend"
    AD_PERFORMANCE = "ad_performance"
    AD_ENTITIES = "ad_entities"
    INVENTORY_SNAPSHOT = "inventory_snapshot"
    REPLENISHMENT_DATA = "replenishment_data"


@dataclass(slots=True)
class McpCallResult:
    """一次 MCP 能力调用的标准化结果和完整追溯信息。"""

    source_id: str
    source_name: str
    capability: McpCapability
    tool_name: str
    collected_at: datetime
    status: str
    records: list[dict]
    field_lineage: list[dict]
    warnings: list[str]
    raw_data: Any
