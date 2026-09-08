"""MCP 原始响应到选品领域字段的适配器。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.selection.contracts import McpCallResult, McpCapability


_KEYWORD_FIELDS: dict[str, tuple[str, ...]] = {
    "keyword": ("keyword",),
    "keyword_translation": ("keywordTranslation", "keyword_translation", "关键词翻译"),
    "ac_recommended": ("acRecommended", "ac_recommended", "AC推荐词"),
    "traffic_share": ("trafficShare", "traffic_share", "流量占比"),
    "traffic_type": ("trafficType", "traffic_type", "流量词类型"),
    "estimated_weekly_impressions": (
        "estimatedWeeklyImpressions",
        "estimated_weekly_impressions",
        "预估周曝光量",
    ),
    "related_product_count": ("relatedProductCount", "related_product_count", "相关产品"),
    "related_asins": ("relatedAsins", "related_asins", "相关ASIN"),
    "aba_weekly_rank": ("abaWeeklyRank", "aba_weekly_rank", "ABA周排名"),
    "search_volume": ("searchVolume", "search_volume", "searches"),
    "monthly_search_volume": ("monthlySearchVolume", "monthly_search_volume", "月搜索量"),
    "monthly_purchase_volume": (
        "monthlyPurchaseVolume",
        "monthly_purchase_volume",
        "月购买量", "purchases",
    ),
    "purchase_rate": ("purchaseRate", "purchase_rate", "购买率"),
    "impressions": ("impressions", "展示量"),
    "clicks": ("clicks", "点击量"),
    "spr": ("spr", "SPR"),
    "title_density": ("titleDensity", "title_density", "标题密度"),
    "trend_rate": ("trendRate", "trend_rate"),
    "trend_period": ("trendPeriod", "trend_period"),
    "product_count": ("products", "productCount", "product_count", "商品数"),
    "competition_index": ("competition", "competitionIndex", "competition_index"),
    "supply_demand_ratio": ("supplyDemandRatio", "supply_demand_ratio", "需供比"),
    "ad_competitor_count": ("adCompetitorCount", "ad_competitor_count", "广告竞品数", "latest7daysAds"),
    "click_share": ("clickShare", "click_share", "点击总占比"),
    "conversion_share": ("conversionShare", "conversion_share", "转化总占比"),
    "cpc": ("cpc", "bid"),
    "ppc_bid": ("ppcBid", "ppc_bid", "PPC竞价"),
    "suggested_bid_range": ("suggestedBidRange", "suggested_bid_range", "建议竞价范围"),
    "conversion_rate": ("conversionRate", "conversion_rate"),
    "relevance_score": ("relevance", "relevanceScore", "relevance_score"),
    "opportunity_score": ("opportunityScore", "opportunity_score"),
    "top_1_asin": ("top1Asin", "top_1_asin", "#1 前三ASIN"),
    "top_1_click_share": ("top1ClickShare", "top_1_click_share", "#1 点击共享"),
    "top_1_conversion_share": (
        "top1ConversionShare",
        "top_1_conversion_share",
        "#1 转化共享",
    ),
    "top_2_asin": ("top2Asin", "top_2_asin", "#2 前三ASIN"),
    "top_2_click_share": ("top2ClickShare", "top_2_click_share", "#2 点击共享"),
    "top_2_conversion_share": (
        "top2ConversionShare",
        "top_2_conversion_share",
        "#2 转化共享",
    ),
    "top_3_asin": ("top3Asin", "top_3_asin", "#3 前三ASIN"),
    "top_3_click_share": ("top3ClickShare", "top_3_click_share", "#3 点击共享"),
    "top_3_conversion_share": (
        "top3ConversionShare",
        "top_3_conversion_share",
        "#3 转化共享",
    ),
    "top_ten_asins": ("topTenAsins", "top_ten_asins", "前十ASIN"),
}

_COMPETITOR_FIELDS: dict[str, tuple[str, ...]] = {
    "asin": ("asin",),
    "title": ("title",),
    "price": ("price",),
    "currency": ("currency",),
    "monthly_sales": ("monthlySales", "monthly_sales"),
    "review_count": ("reviews", "reviewCount", "review_count"),
    "rating": ("rating",),
    "keyword_coverage": ("keywordCoverage", "keyword_coverage"),
}

_EXCHANGE_RATE_FIELDS: dict[str, tuple[str, ...]] = {
    "base_currency": ("base", "baseCurrency", "base_currency"),
    "quote_currency": ("quote", "quoteCurrency", "quote_currency"),
    "rate": ("rate",),
}

_CONTAINER_KEYS = ("result", "data", "items", "records", "list")
_ALL_RAW_FIELDS = {
    raw_name
    for field_map in (_KEYWORD_FIELDS, _COMPETITOR_FIELDS, _EXCHANGE_RATE_FIELDS)
    for raw_names in field_map.values()
    for raw_name in raw_names
}


class SellerSpriteAdapter:
    """将卖家精灵的真实返回字段映射到统一能力记录。"""

    def __init__(self, source_id: str, source_name: str) -> None:
        self.source_id = source_id
        self.source_name = source_name

    def normalize(
        self,
        capability: McpCapability,
        tool_name: str,
        raw_data: Any,
    ) -> McpCallResult:
        """标准化响应；无法解析时返回明确失败，不生成记录。"""
        collected_at = datetime.now(UTC)
        payload, prefix, parse_warning = _decode_text_content(raw_data)
        if parse_warning:
            return self._failure(capability, tool_name, collected_at, raw_data, parse_warning)

        raw_records, found = _extract_records(payload, prefix)
        if not found:
            return self._failure(
                capability,
                tool_name,
                collected_at,
                raw_data,
                "MCP 响应中未找到记录数组",
            )

        field_map = _field_map_for(capability)
        records: list[dict] = []
        lineages: list[dict] = []
        for raw_record, raw_path in raw_records:
            record: dict[str, Any] = dict(raw_record)
            lineage: dict[str, dict[str, Any]] = {}
            for standard_name, raw_names in field_map.items():
                matched_name = next((name for name in raw_names if name in raw_record), None)
                record[standard_name] = (
                    raw_record[matched_name] if matched_name is not None else None
                )
                if matched_name is not None:
                    lineage[standard_name] = {
                        "source_id": self.source_id,
                        "source_name": self.source_name,
                        "tool_name": tool_name,
                        "raw_path": _join_path(raw_path, matched_name),
                    }
            records.append(record)
            lineages.append(lineage)

        return McpCallResult(
            source_id=self.source_id,
            source_name=self.source_name,
            capability=capability,
            tool_name=tool_name,
            collected_at=collected_at,
            status="succeeded",
            records=records,
            field_lineage=lineages,
            warnings=[],
            raw_data=raw_data,
        )

    def _failure(
        self,
        capability: McpCapability,
        tool_name: str,
        collected_at: datetime,
        raw_data: Any,
        warning: str,
    ) -> McpCallResult:
        return McpCallResult(
            source_id=self.source_id,
            source_name=self.source_name,
            capability=capability,
            tool_name=tool_name,
            collected_at=collected_at,
            status="failed",
            records=[],
            field_lineage=[],
            warnings=[warning],
            raw_data=raw_data,
        )


def _field_map_for(capability: McpCapability) -> dict[str, tuple[str, ...]]:
    if capability in {
        McpCapability.COMPETITOR_SEARCH,
        McpCapability.COMPETITOR_METRICS,
    }:
        return _COMPETITOR_FIELDS
    if capability is McpCapability.EXCHANGE_RATE:
        return _EXCHANGE_RATE_FIELDS
    return _KEYWORD_FIELDS


def _decode_text_content(raw_data: Any) -> tuple[Any, str, str | None]:
    if not isinstance(raw_data, dict) or not isinstance(raw_data.get("content"), list):
        return raw_data, "", None

    for index, block in enumerate(raw_data["content"]):
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        text = block.get("text")
        if not isinstance(text, str):
            continue
        try:
            return json.loads(text), f"content[{index}].text.", None
        except json.JSONDecodeError:
            return None, "", "MCP 文本响应不是合法 JSON"
    return raw_data, "", None


def _extract_records(payload: Any, prefix: str) -> tuple[list[tuple[dict, str]], bool]:
    if isinstance(payload, list):
        if not payload:
            return [], True
        if all(isinstance(item, dict) and _looks_like_record(item) for item in payload):
            return [(item, f"{prefix}[{index}]") for index, item in enumerate(payload)], True

        nested_records: list[tuple[dict, str]] = []
        found_nested = False
        for index, item in enumerate(payload):
            records, found = _extract_records(item, f"{prefix}[{index}]")
            nested_records.extend(records)
            found_nested = found_nested or found
        return nested_records, found_nested

    if isinstance(payload, dict):
        if _looks_like_record(payload):
            return [(payload, prefix.rstrip("."))], True
        for key in _CONTAINER_KEYS:
            if key not in payload:
                continue
            child_prefix = _join_path(prefix, key)
            records, found = _extract_records(payload[key], child_prefix)
            if found:
                return records, True
    return [], False


def _looks_like_record(value: dict) -> bool:
    return bool(_ALL_RAW_FIELDS.intersection(value))


def _join_path(prefix: str, name: str) -> str:
    if not prefix or prefix.endswith("."):
        return f"{prefix}{name}"
    return f"{prefix}.{name}"
