# 关键词 MCP 标准字段 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将卖家精灵关键词扩展 MCP 的需求、广告和竞品字段标准化并保留字段追溯信息。

**Architecture:** 扩展 `SellerSpriteAdapter` 的关键词字段别名表，使标准字段写入现有的关键词记录。既有核心指标继续落到 `ResearchKeyword` 固定列，其余指标由现有 `KeywordResearchService` 自动存入 `metrics_json`，不新增数据库迁移。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、pytest。

## Global Constraints

- 生产数据只来自 MCP；Excel 只作为字段与展示参考。
- MCP 缺失字段必须保留为 `None`，禁止补造值。
- 每个已识别字段必须保留 `field_lineage` 原始路径。
- 不修改 `.env`、不提交、不推送。
- 不修改前端和数据库结构。

---

### Task 1: 扩展关键词适配器字段映射

**Files:**
- Modify: `app/selection/adapters.py`
- Modify: `tests/test_selection_mcp.py`

**Interfaces:**
- Consumes: `SellerSpriteAdapter.normalize(capability, tool_name, raw_data) -> McpCallResult`
- Produces: 关键词标准记录，新增字段位于 `McpCallResult.records[index]` 与 `field_lineage[index]`。

- [ ] **Step 1: 写入失败测试**

在 `tests/test_selection_mcp.py` 增加：

```python
def test_keyword_adapter_normalizes_expand_keywords_metrics_and_competitors():
    raw = {"data": [{
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
    }]}

    result = SellerSpriteAdapter("seller", "卖家精灵").normalize(
        McpCapability.KEYWORD_EXPAND, "keyword_research", raw
    )

    assert result.records[0]["keyword_translation"] == "狗碗"
    assert result.records[0]["monthly_search_volume"] == 188462
    assert result.records[0]["ppc_bid"] == "$0.98"
    assert result.records[0]["top_1_asin"] == "B09CGX6WY6"
    assert result.field_lineage[0]["top_ten_asins"]["raw_path"] == "data[0].topTenAsins"
```

- [ ] **Step 2: 运行失败测试**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_selection_mcp.py::test_keyword_adapter_normalizes_expand_keywords_metrics_and_competitors -q`

Expected: FAIL，因为 `keyword_translation`、`monthly_search_volume`、`ppc_bid` 和 `top_1_asin` 尚未在适配器字段表中定义。

- [ ] **Step 3: 扩展字段别名表**

在 `app/selection/adapters.py` 的 `_KEYWORD_FIELDS` 中增加以下标准字段及别名：

```python
"keyword_translation": ("keywordTranslation", "keyword_translation", "关键词翻译"),
"ac_recommended": ("acRecommended", "ac_recommended", "AC推荐词"),
"traffic_share": ("trafficShare", "traffic_share", "流量占比"),
"traffic_type": ("trafficType", "traffic_type", "流量词类型"),
"estimated_weekly_impressions": ("estimatedWeeklyImpressions", "estimated_weekly_impressions", "预估周曝光量"),
"related_product_count": ("relatedProductCount", "related_product_count", "相关产品"),
"related_asins": ("relatedAsins", "related_asins", "相关ASIN"),
"aba_weekly_rank": ("abaWeeklyRank", "aba_weekly_rank", "ABA周排名"),
"monthly_search_volume": ("monthlySearchVolume", "monthly_search_volume", "月搜索量"),
"monthly_purchase_volume": ("monthlyPurchaseVolume", "monthly_purchase_volume", "月购买量"),
"purchase_rate": ("purchaseRate", "purchase_rate", "购买率"),
"impressions": ("impressions", "展示量"),
"clicks": ("clicks", "点击量"),
"spr": ("spr", "SPR"),
"title_density": ("titleDensity", "title_density", "标题密度"),
"supply_demand_ratio": ("supplyDemandRatio", "supply_demand_ratio", "需供比"),
"ad_competitor_count": ("adCompetitorCount", "ad_competitor_count", "广告竞品数"),
"click_share": ("clickShare", "click_share", "点击总占比"),
"conversion_share": ("conversionShare", "conversion_share", "转化总占比"),
"ppc_bid": ("ppcBid", "ppc_bid", "PPC竞价"),
"suggested_bid_range": ("suggestedBidRange", "suggested_bid_range", "建议竞价范围"),
"top_1_asin": ("top1Asin", "top_1_asin", "#1 前三ASIN"),
"top_1_click_share": ("top1ClickShare", "top_1_click_share", "#1 点击共享"),
"top_1_conversion_share": ("top1ConversionShare", "top_1_conversion_share", "#1 转化共享"),
"top_2_asin": ("top2Asin", "top_2_asin", "#2 前三ASIN"),
"top_2_click_share": ("top2ClickShare", "top_2_click_share", "#2 点击共享"),
"top_2_conversion_share": ("top2ConversionShare", "top_2_conversion_share", "#2 转化共享"),
"top_3_asin": ("top3Asin", "top_3_asin", "#3 前三ASIN"),
"top_3_click_share": ("top3ClickShare", "top_3_click_share", "#3 点击共享"),
"top_3_conversion_share": ("top3ConversionShare", "top_3_conversion_share", "#3 转化共享"),
"top_ten_asins": ("topTenAsins", "top_ten_asins", "前十ASIN"),
```

同时将这些字段纳入 `_ALL_RAW_FIELDS` 的识别范围，保持现有缺失字段为 `None` 的行为。

- [ ] **Step 4: 运行映射测试**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_selection_mcp.py -q`

Expected: PASS，且已有缺失字段测试仍验证所有标准键被返回。

### Task 2: 验证关键词服务持久化扩展指标

**Files:**
- Modify: `tests/test_selection_repository.py`
- Test: `tests/test_selection_repository.py`

**Interfaces:**
- Consumes: `_keyword_rows(project_id, run_id, results) -> list[ResearchKeyword]`
- Produces: 扩展指标写入 `ResearchKeyword.metrics_json`，不写入固定数据库列。

- [ ] **Step 1: 写入失败测试**

在 `tests/test_selection_repository.py` 增加：

```python
def test_keyword_rows_keep_extended_mcp_metrics_in_metrics_json():
    result = McpCallResult(
        source_id="seller",
        source_name="卖家精灵",
        capability=McpCapability.KEYWORD_EXPAND,
        tool_name="keyword_research",
        collected_at=datetime.now(UTC),
        status="succeeded",
        records=[{"keyword": "dog bowls", "monthly_search_volume": 188462, "ppc_bid": "$0.98"}],
        field_lineage=[{}],
        warnings=[],
        raw_data={},
    )

    row = _keyword_rows(1, 2, [result])[0]

    assert row.search_volume is None
    assert row.metrics_json["monthly_search_volume"] == 188462
    assert row.metrics_json["ppc_bid"] == "$0.98"
```

- [ ] **Step 2: 运行失败测试**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_selection_repository.py::test_keyword_rows_keep_extended_mcp_metrics_in_metrics_json -q`

Expected: PASS 或 FAIL。若已通过，说明现有存储边界已经满足设计，不修改生产代码。

- [ ] **Step 3: 运行完整相关测试**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_selection_mcp.py tests/test_selection_repository.py tests/test_selection_api.py -q`

Expected: PASS。
