# 关键词 MCP 标准字段设计

## 目标

将卖家精灵关键词扩展结果标准化为稳定的数据契约，供 AI 选品关键词调研接口与后续表格前端使用。参考文件为 `ExpandKeywords-US-B0G49YLYSK-batch(5)-202607-134684.xlsx` 的主工作表。

## 范围

- 仅修改 MCP 响应到选品关键词记录的字段映射。
- 不修改前端页面。
- 不新增数据库列或迁移。
- 不将 Excel 作为生产数据源；生产数据仍只来自配置的 MCP。

## 数据存储

现有稳定核心字段继续写入 `ResearchKeyword` 的数据库列：

- `search_volume`
- `trend_rate`
- `trend_period`
- `product_count`
- `competition_index`
- `cpc`
- `conversion_rate`
- `relevance_score`
- `opportunity_score`

扩展字段写入 `metrics_json`，并在 `field_lineage_json` 中保存对应 MCP 原始路径。

## 扩展字段

| 分组 | 标准字段 |
| --- | --- |
| 关键词与归因 | `keyword_translation`、`ac_recommended`、`traffic_share`、`traffic_type`、`estimated_weekly_impressions`、`related_product_count`、`related_asins`、`aba_weekly_rank` |
| 需求与竞争 | `monthly_search_volume`、`monthly_purchase_volume`、`purchase_rate`、`impressions`、`clicks`、`spr`、`title_density`、`supply_demand_ratio`、`ad_competitor_count` |
| 流量与广告 | `click_share`、`conversion_share`、`ppc_bid`、`suggested_bid_range` |
| 竞品格局 | `top_1_asin`、`top_1_click_share`、`top_1_conversion_share`、`top_2_asin`、`top_2_click_share`、`top_2_conversion_share`、`top_3_asin`、`top_3_click_share`、`top_3_conversion_share`、`top_ten_asins` |

## 映射与失败规则

- 适配器支持卖家精灵常见的 camelCase、snake_case 与 Excel 中文列名别名。
- MCP 未返回某字段时，该标准字段为 `None`，不推导、不填充示例值。
- 原始记录保留在 `SourceSnapshot`，字段来源路径保留在 `field_lineage_json`。
- 未找到任何可识别关键词记录时，适配器明确返回失败结果。

## 验证

- 新增适配器单测：一个模拟 MCP 记录同时包含需求、广告和竞品字段。
- 断言标准化记录、字段追溯路径和未识别字段行为。
- 运行 `tests/test_selection_mcp.py` 与关键词服务相关测试。
