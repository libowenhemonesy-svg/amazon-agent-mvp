# 卖家精灵 MCP 全量响应前端展示设计

## 目标

AI 选品不再依赖旧的通用 MCP 能力映射模板。系统直接调用已验证的卖家精灵工具，保留其完整响应，并在前端展示所有返回内容。

## 数据流

1. 用户选择输入类型。
   - ASIN：调用 `traffic_extend`，请求体使用 `request.asinList`、`request.marketplace` 与显式 `request.queryType=2`。
   - 种子词：调用 `keyword_miner`，请求体使用 `request.keyword` 与 `request.marketplace`。
   - 类目：先调用 `product_node` 解析类目节点，再调用 `keyword_research` 取得该节点的关键词结果。
2. 对带有 `data.pages` 的响应，从第 1 页循环到最后一页，合并 `data.items`，并按 `keyword` 去重。
3. 每一页的完整原始 MCP 响应写入来源快照；关键词记录保存完整原始条目，而不是仅保留预定义字段。
4. 前端同时呈现：
   - 关键词表：固定核心列，便于选择和筛选；
   - 完整字段表：由真实响应字段动态生成列；
   - 原始响应面板：可展开查看每个工具、每一页的完整 JSON、页码、总数与错误消息。

## 错误处理

- MCP 的 `isError`、非成功状态和解析异常均展示实际错误文本。
- 若任一页失败，保留已成功页的数据，并把本次运行标记为部分失败。
- 不生成固定关键词、示例数据或兜底分析。

## 验证标准

- ASIN `B0G49YLYSK` 的 `traffic_extend` 请求显式包含 `queryType=2`。
- 对 MCP 返回的 `pages=5`，系统请求 5 页并聚合所有 `items`。
- 未被固定字段映射覆盖的 MCP 字段仍能在 API 响应与前端原始数据面板中看到。
- 前端不再将真实 MCP 错误折叠为“所有 MCP 数据源均未返回可用关键词”。
