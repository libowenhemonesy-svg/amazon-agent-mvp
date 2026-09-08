# 卖家精灵 MCP 全量响应前端展示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AI 选品直接调用卖家精灵 MCP，采集三类关键词输入的所有分页数据，并在前端展示完整原始响应。

**Architecture:** 新增卖家精灵关键词采集器，直接依据已验证的 MCP 工具 Schema 构造嵌套请求，不读取旧能力映射 JSON。关键词服务使用采集器的聚合结果保存关键词和完整原始响应；前端固定显示核心关键词表，同时动态显示所有 MCP 字段和原始 JSON。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、Vanilla JavaScript、pytest、卖家精灵 Streamable HTTP MCP。

## Global Constraints

- 不修改 `.env`，不输出 API Key、Token、Cookie 或请求头。
- 不生成固定关键词、示例数据或假装成功的 MCP 结果。
- 只修改 AI 选品、卖家精灵 MCP 接入及其直接测试。
- 不提交或推送 Git 变更。

---

### Task 1: 卖家精灵关键词采集器与分页测试

**Files:**
- Create: `app/selection/sellersprite_keywords.py`
- Modify: `tests/test_selection_mcp.py`

**Interfaces:**
- Produces: `SellerSpriteKeywordCollector.collect(input_type: str, input_value: str, marketplace: str) -> list[McpCallResult]`
- Consumes: `StreamableHttpMCPClient.call_tool(tool_name: str, arguments: dict) -> Awaitable[dict]`

- [ ] **Step 1: 写入失败测试，定义 ASIN 请求和分页聚合行为**

```python
def test_collector_calls_traffic_extend_for_every_page():
    client = FakeMcpClient([
        {"content": [{"type": "text", "text": '{"code":"OK","data":{"pages":2,"page":1,"items":[{"keyword":"dog bowls"}]}}'}]},
        {"content": [{"type": "text", "text": '{"code":"OK","data":{"pages":2,"page":2,"items":[{"keyword":"dog bowl"}]}}'}]},
    ])
    collector = SellerSpriteKeywordCollector(client)

    results = asyncio.run(collector.collect("asin", "B0G49YLYSK", "US"))

    assert [call[0] for call in client.calls] == ["traffic_extend", "traffic_extend"]
    assert client.calls[0][1] == {"request": {"asinList": ["B0G49YLYSK"], "marketplace": "US", "queryType": 2, "page": 1}}
    assert client.calls[1][1]["request"]["page"] == 2
    assert [row["keyword"] for row in results[0].records] == ["dog bowls", "dog bowl"]
```

- [ ] **Step 2: 运行失败测试，确认因采集器不存在而失败**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_selection_mcp.py::test_collector_calls_traffic_extend_for_every_page -q`

Expected: FAIL，提示 `SellerSpriteKeywordCollector` 无法导入。

- [ ] **Step 3: 写入失败测试，定义种子词和类目调用链**

```python
def test_collector_uses_keyword_miner_for_seed_and_resolves_category_node():
    client = FakeMcpClient.with_named_responses({
        "keyword_miner": _page([{"keyword": "portable fan"}]),
        "product_node": _nodes([{"nodeIdPath": "123:456"}]),
        "keyword_research": _page([{"keyword": "quiet fan"}]),
    })
    collector = SellerSpriteKeywordCollector(client)

    seed = asyncio.run(collector.collect("seed", "portable fan", "US"))
    category = asyncio.run(collector.collect("category", "Fans", "US"))

    assert client.calls[0] == ("keyword_miner", {"request": {"keyword": "portable fan", "marketplace": "US", "page": 1}})
    assert ("product_node", {"request": {"keyword": "Fans", "marketplace": "US"}}) in client.calls
    assert any(name == "keyword_research" and call["request"]["departments"] == ["123:456"] for name, call in client.calls)
    assert seed[0].records[0]["keyword"] == "portable fan"
    assert category[-1].records[0]["keyword"] == "quiet fan"
```

- [ ] **Step 4: 实现最小采集器**

```python
class SellerSpriteKeywordCollector:
    async def collect(self, input_type: str, input_value: str, marketplace: str) -> list[McpCallResult]:
        if input_type == "asin":
            return [await self._collect_pages("traffic_extend", {"asinList": [input_value], "marketplace": marketplace, "queryType": 2})]
        if input_type == "seed":
            return [await self._collect_pages("keyword_miner", {"keyword": input_value, "marketplace": marketplace})]
        return await self._collect_category(input_value, marketplace)
```

`_collect_pages` 首次请求 `page=1`，从响应 `data.pages` 读取最后页，顺序调用后续页，合并 `data.items` 并按 `keyword` 去重；每页完整响应放入聚合结果的 `raw_data["pages"]`。`_collect_category` 先调用 `product_node`，读取首个 `nodeIdPath`，再调用 `keyword_research`。

- [ ] **Step 5: 运行采集器测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_selection_mcp.py -q`

Expected: PASS。

### Task 2: 关键词服务改用直接采集器并保存所有原始字段

**Files:**
- Modify: `app/selection/keyword_service.py`
- Modify: `app/routes/selection.py`
- Modify: `tests/test_selection_api.py`

**Interfaces:**
- Consumes: `SellerSpriteKeywordCollector.collect(...) -> list[McpCallResult]`
- Produces: `GET /api/selection/projects/{project_id}/keyword-runs/{run_id}` 和关键词调研 POST 响应中的 `keywords[].metrics`、`snapshots[].response`。

- [ ] **Step 1: 写入失败测试，要求未知 MCP 字段保存并返回**

```python
def test_keyword_research_preserves_every_mcp_record_field(client_as_user, fake_collector):
    fake_collector.results = [mcp_result(records=[{
        "keyword": "dog bowls", "searches": 187866, "unknown_nested": {"x": 1}
    }])]
    project = _create_project(client_as_user)

    response = client_as_user.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": "all-fields"},
        json={"input_type": "asin", "input_value": "B0G49YLYSK"},
    )

    assert response.json()["keywords"][0]["metrics"]["searches"] == 187866
    assert response.json()["keywords"][0]["metrics"]["unknown_nested"] == {"x": 1}
```

- [ ] **Step 2: 运行失败测试，确认未知字段当前没有保存**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_selection_api.py::test_keyword_research_preserves_every_mcp_record_field -q`

Expected: FAIL，`metrics` 中缺少 `searches` 或 `unknown_nested`。

- [ ] **Step 3: 最小化改造服务依赖和记录保存**

```python
class KeywordResearchService:
    def __init__(self, session: Session, collector: SellerSpriteKeywordCollector) -> None:
        self.collector = collector

    # run 内：
    results = await self.collector.collect(normalized_type, cleaned_value, cleaned_marketplace)
```

在 MCP 适配器中以原始条目为基础构建标准记录：`record = dict(raw_record)`，再写入标准字段别名。`_keyword_rows` 将除数据库模型列外的全部字段写入 `metrics_json`。`_run_detail` 使用 `_snapshot(snapshot, full=True)`，让调研接口直接返回每个来源快照的完整响应。

- [ ] **Step 4: 运行 API 测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_selection_api.py -q`

Expected: PASS。

### Task 3: MCP 实际字段别名与真实错误透传

**Files:**
- Modify: `app/selection/adapters.py`
- Modify: `app/selection/keyword_service.py`
- Modify: `tests/test_selection_mcp.py`

**Interfaces:**
- Produces: `McpCallResult.records`，其中既有原始键，也有 `search_volume`、`monthly_purchase_volume`、`cpc` 等标准字段。

- [ ] **Step 1: 写入失败测试，定义 `traffic_extend` 实际字段映射**

```python
def test_adapter_maps_traffic_extend_response_without_discarding_raw_fields():
    raw = {"data": [{"keyword": "dog bowls", "searches": 187866, "purchases": 6049, "bid": 0.94, "latest7daysAds": 296}]}

    result = SellerSpriteAdapter("seller-sprite", "卖家精灵").normalize(
        McpCapability.ASIN_KEYWORD_REVERSE, "traffic_extend", raw
    )

    assert result.records[0]["search_volume"] == 187866
    assert result.records[0]["monthly_purchase_volume"] == 6049
    assert result.records[0]["cpc"] == 0.94
    assert result.records[0]["ad_competitor_count"] == 296
    assert result.records[0]["latest7daysAds"] == 296
```

- [ ] **Step 2: 运行失败测试，确认别名尚未支持**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_selection_mcp.py::test_adapter_maps_traffic_extend_response_without_discarding_raw_fields -q`

Expected: FAIL，标准字段为 `None`。

- [ ] **Step 3: 实现字段别名与 MCP 错误识别**

```python
"search_volume": ("searchVolume", "search_volume", "searches"),
"monthly_purchase_volume": ("monthlyPurchaseVolume", "monthly_purchase_volume", "purchases"),
"cpc": ("cpc", "bid"),
"ad_competitor_count": ("adCompetitorCount", "ad_competitor_count", "latest7daysAds"),
```

当响应是 `{ "isError": true, "content": [{"type": "text", "text": "..."}] }` 时，生成失败结果并把该文本置入 `warnings`。关键词服务将每个失败结果的 `warnings` 合并为 `error_summary`，而非固定使用“所有 MCP 数据源调用失败”。

- [ ] **Step 4: 运行 MCP 适配器测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_selection_mcp.py -q`

Expected: PASS。

### Task 4: AI 选品前端动态字段表与原始响应面板

**Files:**
- Modify: `app/static/selection-workbench.js`
- Modify: `app/static/selection-workbench.css`
- Modify: `app/static/index.html`
- Modify: `tests/test_selection_frontend.py`

**Interfaces:**
- Consumes: 关键词调研响应的 `keywords[].metrics` 和 `snapshots[].response`。
- Produces: 动态字段表、可展开原始 JSON 面板和真实错误消息。

- [ ] **Step 1: 写入失败静态前端测试**

```python
def test_selection_frontend_renders_dynamic_mcp_fields_and_raw_snapshots():
    app_js = (PROJECT_ROOT / "app" / "static" / "selection-workbench.js").read_text(encoding="utf-8")
    index_html = (PROJECT_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")

    assert "renderMcpFields" in app_js
    assert "renderMcpRawSnapshots" in app_js
    assert 'id="selection-mcp-fields"' in index_html
    assert 'id="selection-mcp-raw"' in index_html
```

- [ ] **Step 2: 运行失败测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_selection_frontend.py::test_selection_frontend_renders_dynamic_mcp_fields_and_raw_snapshots -q`

Expected: FAIL，缺少动态渲染函数或容器。

- [ ] **Step 3: 实现前端动态展示**

```javascript
function renderMcpFields() {
  const rows = selectionState.keywordRows;
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row.metrics || {})))];
  document.getElementById("selection-mcp-fields").innerHTML = renderDynamicTable(columns, rows);
}

function renderMcpRawSnapshots() {
  document.getElementById("selection-mcp-raw").innerHTML = selectionState.snapshots
    .map((snapshot) => `<details><summary>${escapeHtml(snapshot.tool_name)} · ${escapeHtml(snapshot.collected_at)}</summary><pre>${escapeHtml(JSON.stringify(snapshot.response, null, 2))}</pre></details>`)
    .join("");
}
```

在关键词调研完成、项目加载和错误状态更新时调用两个函数。运行失败时，优先显示 `data.error_summary` 和快照中的 `warnings`，不显示固定的空关键词文案。

- [ ] **Step 4: 运行前端测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_selection_frontend.py -q`

Expected: PASS。

### Task 5: 端到端回归验证

**Files:**
- Modify: `tests/test_selection_api.py`
- Modify: `tests/test_selection_frontend.py`

**Interfaces:**
- Verifies: ASIN、种子词、类目三种输入均不依赖旧能力映射；分页、完整字段与真实错误均能通过 API 到达前端。

- [ ] **Step 1: 写入失败回归测试**

```python
def test_asin_research_returns_paginated_mcp_raw_data_and_all_fields(client_as_user, fake_collector):
    fake_collector.results = [_result_with_pages_and_fields()]
    project = _create_project(client_as_user)

    response = client_as_user.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": "pagination"},
        json={"input_type": "asin", "input_value": "B0G49YLYSK"},
    )

    assert response.json()["snapshots"][0]["response"]["pages"][0]["data"]["page"] == 1
    assert response.json()["snapshots"][0]["response"]["pages"][1]["data"]["page"] == 2
```

- [ ] **Step 2: 运行失败测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_selection_api.py::test_asin_research_returns_paginated_mcp_raw_data_and_all_fields -q`

Expected: FAIL，响应未包含完整分页原始数据。

- [ ] **Step 3: 补齐最小实现并运行全部相关测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_selection_mcp.py tests/test_selection_api.py tests/test_selection_frontend.py -q`

Expected: PASS。

- [ ] **Step 4: 运行语法验证**

Run: `./.venv/Scripts/python.exe -m compileall app tests`

Expected: PASS。
