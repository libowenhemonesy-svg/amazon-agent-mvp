# AI 选品工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 AI 选品页面重建为只使用 MCP 数据源、可保存项目、依次完成关键词调研、产品方向、成本定价和决策报告的完整工作台。

**Architecture:** 新建 `app/selection/` 领域包，使用统一 MCP 能力与标准字段模型隔离不同数据源；FastAPI 路由只负责认证、校验和序列化，计算与持久化放在独立服务中。前端保持 Vanilla JS，但将选品逻辑拆出为独立静态资源，避免继续膨胀 `app/static/app.js`。

**Tech Stack:** Python 3.11、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、httpx、LangChain MCP adapters、Vanilla JS/CSS、pytest。

## Global Constraints

- 所有用户可见文案、回复和代码注释使用中文；Python/JavaScript 标识符保持英文。
- 不修改 `.env`，不输出或记录 API Key、Token、Cookie、自定义认证头。
- 不提交、不推送、不重置 Git；每个任务完成后仅报告变更和测试结果，除非用户另行明确授权。
- 保留用户现有无关改动；只修改本计划列出的文件和必要直接依赖。
- 真实 MCP、汇率或 LLM 不可用时明确失败，不生成模拟数据、固定评分或固定建议。
- 前端继续使用 `app/static/` 下的 Vanilla JS/CSS，不引入新前端框架。
- 生产数据库结构使用 Alembic；SQLite 开发环境通过 `Base.metadata.create_all()` 与必要兼容逻辑工作。
- 所有项目数据按认证用户隔离，路由不得依赖前端隐藏完成权限控制。

---

## File Structure

### 新建

- `app/selection/__init__.py`：领域包导出。
- `app/selection/contracts.py`：MCP 能力、标准记录和来源追溯类型。
- `app/selection/repository.py`：选品项目及阶段数据的数据库读写。
- `app/selection/mcp_registry.py`：多 MCP 配置加载、能力匹配和调用编排。
- `app/selection/adapters.py`：卖家精灵首个适配器及通用字段映射。
- `app/selection/credentials.py`：MCP 凭据引用的服务端读写和脱敏边界。
- `app/selection/keyword_service.py`：关键词研究、去重、筛选和保存。
- `app/selection/direction_service.py`：多关键词聚类、竞品聚合和数据完整度。
- `app/selection/pricing.py`：运费、汇率和定价纯函数。
- `app/selection/scoring.py`：固定六维评分和结论。
- `app/selection/report_service.py`：规则结果与真实 LLM 报告编排。
- `app/routes/selection.py`：项目制选品 API。
- `app/static/selection-workbench.js`：四阶段前端状态与 API 调用。
- `app/static/selection-workbench.css`：选品工作台专属样式。
- `alembic/versions/0004_selection_workbench.py`：数据库迁移。
- `tests/test_selection_repository.py`
- `tests/test_selection_pricing.py`
- `tests/test_selection_scoring.py`
- `tests/test_selection_mcp.py`
- `tests/test_selection_api.py`
- `tests/test_selection_report.py`
- `tests/conftest.py`：认证客户端、内存数据库和选品对象工厂。

### 修改

- `app/db/models.py`：增加选品项目相关 ORM 模型。
- `app/main.py`：注册新路由和服务，移除旧 Chrome 选品路由。
- `app/routes/settings.py`：单 MCP 设置升级为多数据源 CRUD 与连接测试。
- `app/agents/product_research_agent.py`：移除卖家精灵写死文案，复用统一 MCP 研究服务。
- `app/static/index.html`：替换旧 AI 选品 DOM，引入独立 JS/CSS。
- `app/static/app.js`：移除旧 Chrome 选品和原始 JSON 渲染逻辑。
- `app/static/styles.css`：移除只服务旧选品页面的样式。
- `tests/test_api.py`：更新静态页面与旧路由回归断言。
- `tests/test_mcp_tools.py`、`tests/test_product_research_agent.py`：迁移到通用数据源命名。

### 删除（仅在 `rg` 确认无其他消费者后）

- `app/routes/chrome.py`：旧 Chrome 采集与固定 AI 分析路由。
- `app/agents/product_research_mcp.py`：由 `app/selection/mcp_registry.py` 和适配器替代。
- `app/analysis/product_research.py`：旧规则估算与固定兜底实现。

---

### Task 1: 建立选品数据库模型、迁移和仓储

**Files:**
- Create: `alembic/versions/0004_selection_workbench.py`
- Create: `app/selection/__init__.py`
- Create: `app/selection/repository.py`
- Create: `tests/conftest.py`
- Modify: `app/db/models.py`
- Test: `tests/test_selection_repository.py`

**Interfaces:**
- Produces: `SelectionRepository.create_project(user_id: str, name: str, marketplace: str, target_currency: str) -> SelectionProject`
- Produces: `SelectionRepository.list_projects(user_id: str) -> list[SelectionProject]`
- Produces: `SelectionRepository.replace_selected_keywords(project_id: int, user_id: str, keyword_ids: list[int]) -> list[ResearchKeyword]`
- Produces ORM models named in section 6 of the approved specification.

- [ ] **Step 1: Write failing repository tests**

```python
def test_project_and_selected_keywords_are_scoped_to_user(session):
    repo = SelectionRepository(session)
    project = repo.create_project("alice", "便携风扇", "US", "USD")
    run = repo.create_keyword_run(project.id, "alice", "seed", "portable fan", "US", "all")
    rows = repo.replace_keyword_results(
        run.id,
        "alice",
        [{"keyword": "portable fan", "normalized_keyword": "portable fan", "search_volume": 42000}],
    )
    selected = repo.replace_selected_keywords(project.id, "alice", [rows[0].id])
    assert selected[0].selected is True
    assert repo.list_projects("bob") == []
```

Add reusable test fixtures in `tests/conftest.py`: an in-memory application, SQLAlchemy session, `client_as_user`, `client_as_admin`, and helpers that override `get_current_user` with `UserInfo`. Each fixture must clear dependency overrides after yielding.

- [ ] **Step 2: Run the failing test**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_selection_repository.py -q`

Expected: FAIL because selection models and repository do not exist.

- [ ] **Step 3: Add explicit ORM models**

Add `SelectionProject`, `McpDataSource`, `KeywordResearchRun`, `ResearchKeyword`, `ProductDirection`, `FreightTemplate`, `ExchangeRate`, `PricingSnapshot`, `SelectionReport`, and `SourceSnapshot` to `app/db/models.py`. Use `user_id: Mapped[str] = mapped_column(String(64), index=True)` to match the existing authenticated username identity.

Representative constraints:

```python
class ResearchKeyword(Base):
    __tablename__ = "research_keywords"
    __table_args__ = (
        UniqueConstraint("run_id", "normalized_keyword", name="uq_research_keyword_run_word"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    keyword: Mapped[str] = mapped_column(String(512))
    normalized_keyword: Mapped[str] = mapped_column(String(512))
    search_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    field_lineage_json: Mapped[dict] = mapped_column(JSON, default=dict)
    selected: Mapped[bool] = mapped_column(default=False)
```

- [ ] **Step 4: Implement repository ownership checks and transactional writes**

```python
def get_owned_project(self, project_id: int, user_id: str) -> SelectionProject:
    project = self.session.scalar(
        select(SelectionProject).where(
            SelectionProject.id == project_id,
            SelectionProject.user_id == user_id,
        )
    )
    if project is None:
        raise LookupError("选品项目不存在")
    return project
```

Repository methods must call `flush()` while composing a stage and commit once at the stage boundary.

- [ ] **Step 5: Add Alembic migration**

Set `revision = "0004_selection_workbench"` and `down_revision = "0003_memory_tables"`. Create all ten tables and their project/user/status/time indexes. The downgrade drops only these new tables in reverse dependency order.

- [ ] **Step 6: Verify repository and migration**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_selection_repository.py -q
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Expected: repository tests PASS; Alembic reaches `0004_selection_workbench` without errors.

- [ ] **Step 7: Review checkpoint**

Inspect `git diff -- app/db/models.py app/selection/repository.py alembic/versions/0004_selection_workbench.py tests/test_selection_repository.py`. Do not stage or commit.

---

### Task 2: 实现运费、汇率和定价纯函数

**Files:**
- Create: `app/selection/pricing.py`
- Test: `tests/test_selection_pricing.py`

**Interfaces:**
- Produces: `calculate_billable_weight(actual_weight_kg: Decimal, length_cm: Decimal, width_cm: Decimal, height_cm: Decimal, volume_divisor: Decimal, minimum_weight_kg: Decimal) -> Decimal`
- Produces: `calculate_freight(weight_kg: Decimal, template: FreightRule) -> Decimal`
- Produces: `calculate_target_price(input: PricingInput) -> PricingResult`

- [ ] **Step 1: Write failing formula tests**

```python
def test_target_price_uses_net_margin_and_commission():
    result = calculate_target_price(
        PricingInput(
            product_cost=Decimal("30"),
            domestic_shipping=Decimal("0"),
            international_shipping=Decimal("15"),
            exchange_rate=Decimal("1"),
            commission_rate=Decimal("0.15"),
            target_net_margin=Decimal("0.40"),
        )
    )
    assert result.target_price == Decimal("100.00")
    assert result.commission_amount == Decimal("15.00")
    assert result.net_profit_amount == Decimal("40.00")

def test_billable_weight_takes_larger_of_actual_and_volume():
    weight = calculate_billable_weight(
        Decimal("0.10"), Decimal("60"), Decimal("40"), Decimal("30"),
        Decimal("6000"), Decimal("0"),
    )
    assert weight == Decimal("12")
```

- [ ] **Step 2: Verify tests fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_selection_pricing.py -q`

Expected: FAIL because `app.selection.pricing` does not exist.

- [ ] **Step 3: Implement decimal-based calculations**

```python
denominator = Decimal("1") - data.commission_rate - data.target_net_margin
if denominator <= 0:
    raise ValueError("平台佣金率与净利润率之和必须小于 100%")
target_price = money((converted_cost + converted_freight) / denominator)
```

Use `Decimal` throughout, round currency with `ROUND_HALF_UP`, and support `per_kg` plus `first_additional` freight modes.

- [ ] **Step 4: Add invalid-input and tiered-freight tests**

Cover zero/negative divisor, `commission + margin >= 1`, minimum chargeable weight, first weight, and rounded additional-weight units.

- [ ] **Step 5: Run pricing tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_selection_pricing.py -q`

Expected: all pricing tests PASS.

- [ ] **Step 6: Review checkpoint**

Inspect pricing code for float usage and hidden defaults. Do not stage or commit.

---

### Task 3: 定义 MCP 能力契约和卖家精灵适配器

**Files:**
- Create: `app/selection/contracts.py`
- Create: `app/selection/adapters.py`
- Create: `app/selection/mcp_registry.py`
- Modify: `app/agents/mcp_tools.py`
- Test: `tests/test_selection_mcp.py`

**Interfaces:**
- Produces: `McpCapability` enum with the eight approved capability values.
- Produces: `McpCallResult(source_id: str, source_name: str, capability: McpCapability, tool_name: str, collected_at: datetime, status: str, records: list[dict], field_lineage: list[dict], warnings: list[str], raw_data: Any)`.
- Produces: `McpRegistry.call(capability: McpCapability, arguments: dict[str, Any]) -> list[McpCallResult]`.

- [ ] **Step 1: Write adapter tests using real-shaped MCP envelopes**

```python
@pytest.mark.asyncio
async def test_keyword_adapter_keeps_records_and_lineage():
    adapter = SellerSpriteAdapter(source_id="seller", source_name="卖家精灵")
    result = adapter.normalize(
        McpCapability.KEYWORD_EXPAND,
        "keyword_research",
        {"data": [{"keyword": "portable fan", "searchVolume": 42000}]},
    )
    assert result.records[0]["keyword"] == "portable fan"
    assert result.records[0]["search_volume"] == 42000
    assert result.field_lineage[0]["search_volume"]["raw_path"] == "data[0].searchVolume"
```

Add fixtures for `content: [{"type": "text", "text": "{\"data\":[{\"keyword\":\"portable fan\"}]}"}]`, nested result arrays, missing fields, invalid JSON text, and source timeout.

- [ ] **Step 2: Verify tests fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_selection_mcp.py -q`

Expected: FAIL because contracts and adapters do not exist.

- [ ] **Step 3: Implement explicit capability and result types**

```python
class McpCapability(StrEnum):
    KEYWORD_EXPAND = "keyword_expand"
    ASIN_KEYWORD_REVERSE = "asin_keyword_reverse"
    CATEGORY_KEYWORDS = "category_keywords"
    KEYWORD_METRICS = "keyword_metrics"
    KEYWORD_TREND = "keyword_trend"
    COMPETITOR_SEARCH = "competitor_search"
    COMPETITOR_METRICS = "competitor_metrics"
    EXCHANGE_RATE = "exchange_rate"
```

Adapters must map only fields that actually exist. Unknown fields remain in `raw_data`; missing standard fields remain `None`.

- [ ] **Step 4: Replace heuristic “highest scoring tool” selection**

`McpRegistry` reads each source's `capability_config_json` and calls the explicitly configured tool. If a capability has no tool mapping, return a capability-not-supported result instead of guessing from tool descriptions.

- [ ] **Step 5: Keep a compatibility bridge for existing environment config**

Allow the current single `MCP_SERVER_*` or `SELLERSPRITE_*` variables to materialize one runtime source named “卖家精灵” until the administrator saves database-backed sources. Do not rename or write `.env` in this task.

- [ ] **Step 6: Run MCP tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_selection_mcp.py tests/test_mcp_tools.py -q`

Expected: all tests PASS; no production path exposes `StaticLLMClient` or fabricated MCP records.

- [ ] **Step 7: Review checkpoint**

Search with `rg -n "highest|demo|mock|固定|sellersprite_mcp" app/selection app/agents/mcp_tools.py`. Any legacy name must be limited to compatibility input, not normalized output or UI contracts.

---

### Task 4: 升级多 MCP 设置与凭据边界

**Files:**
- Create: `app/selection/credentials.py`
- Modify: `app/routes/settings.py`
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `McpDataSource` ORM and `McpRegistry`.
- Produces: `GET/POST/PATCH /api/settings/mcp-sources` and `POST /api/settings/mcp-sources/{id}/test`.

- [ ] **Step 1: Write failing API tests**

```python
def test_admin_can_create_multiple_mcp_sources(client_as_admin):
    first = client_as_admin.post("/api/settings/mcp-sources", json={
        "name": "卖家精灵", "url": "https://mcp.example/one", "transport": "streamable_http",
        "priority": 10, "enabled": True, "capabilities": {"keyword_expand": {"tool": "keyword_research"}},
    })
    second = client_as_admin.post("/api/settings/mcp-sources", json={
        "name": "趋势数据", "url": "https://mcp.example/two", "transport": "streamable_http",
        "priority": 20, "enabled": True, "capabilities": {"keyword_trend": {"tool": "trend"}},
    })
    assert first.status_code == second.status_code == 201
    assert len(client_as_admin.get("/api/settings/mcp-sources").json()["items"]) == 2
```

Also assert non-admin receives 403 and list responses never contain API keys or custom header values.

- [ ] **Step 2: Verify tests fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api.py -k "mcp_sources" -q`

Expected: FAIL with 404.

- [ ] **Step 3: Implement authenticated CRUD**

Use `Depends(get_current_admin)`. Validate URL, transport, unique display name, positive priority, and capability mapping shape. Store only a `credential_reference` on `McpDataSource`; obtain secret values from the server credential layer and never serialize them.

Implement `EnvCredentialStore` as the first credential backend. A reference is a stable prefix such as `MCP_SOURCE_12`; its secret values are `${prefix}_API_KEY` and `${prefix}_HEADERS`. The route may call the existing server-side env-file updater when an administrator explicitly saves credentials through the settings UI, but implementation commands must never directly edit `.env`.

```python
class EnvCredentialStore:
    def __init__(self, env: Mapping[str, str], updater: Callable[[dict[str, str]], None]):
        self.env = env
        self.updater = updater

    def save(self, reference: str, *, api_key: str, headers: dict[str, str]) -> None:
        updates = {}
        if api_key:
            updates[f"{reference}_API_KEY"] = api_key
        if headers:
            updates[f"{reference}_HEADERS"] = json.dumps(headers, ensure_ascii=False)
        if updates:
            self.updater(updates)

    def load_headers(self, reference: str) -> dict[str, str]:
        headers = json.loads(self.env.get(f"{reference}_HEADERS", "{}"))
        api_key = self.env.get(f"{reference}_API_KEY", "").strip()
        if api_key:
            headers.setdefault("Authorization", f"Bearer {api_key}")
        return {str(key): str(value) for key, value in headers.items()}

    def configured(self, reference: str) -> bool:
        return bool(
            self.env.get(f"{reference}_API_KEY")
            or self.env.get(f"{reference}_HEADERS")
        )
```

`POST /api/settings/mcp-sources` accepts optional `api_key` and `headers`; response returns only `credentials_configured: bool`. Updating a source with blank credential fields preserves existing credentials.

- [ ] **Step 4: Implement connection test**

Connection test performs initialize, `tools/list`, and verifies every configured capability tool exists. Return tool names and missing mappings, not full sensitive schemas or headers.

- [ ] **Step 5: Update MCP settings UI**

Render multiple source rows with name, supported capability count, connection state, priority, enable toggle and edit action. Keep the existing Codex-style list visual; do not put provider-specific fields in AI 选品页面.

- [ ] **Step 6: Run settings tests and JavaScript syntax check**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api.py -k "mcp" -q
node --check app\static\app.js
```

Expected: tests PASS and Node exits 0.

- [ ] **Step 7: Review checkpoint**

Verify `rg -n "api_key|Authorization|headers" app/routes/settings.py` shows no response serialization or logging of credential values.

---

### Task 5: 实现关键词研究服务与项目 API

**Files:**
- Create: `app/selection/keyword_service.py`
- Create: `app/routes/selection.py`
- Modify: `app/main.py`
- Test: `tests/test_selection_api.py`

**Interfaces:**
- Consumes: `SelectionRepository`, `McpRegistry`, `McpCapability`.
- Produces: project CRUD, keyword research, keyword list and selected-keyword APIs from the spec.
- Produces: `KeywordResearchService.run(project_id: int, user_id: str, input_type: str, input_value: str, marketplace: str, category: str | None, request_id: str) -> KeywordResearchRun`.

- [ ] **Step 1: Write failing authenticated flow test**

```python
def test_keyword_research_saves_normalized_rows_and_raw_snapshot(app, client, fake_registry):
    app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="alice", display_name="Alice", role="user", is_active=True
    )
    project = client.post("/api/selection/projects", json={
        "name": "便携风扇", "marketplace": "US", "target_currency": "USD"
    }).json()
    response = client.post(
        f"/api/selection/projects/{project['id']}/keyword-research",
        headers={"Idempotency-Key": "research-1"},
        json={"input_type": "seed", "input_value": "portable fan", "category": "all"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["keywords"][0]["source_name"] == "卖家精灵"
```

- [ ] **Step 2: Verify tests fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_selection_api.py -k "keyword" -q`

Expected: FAIL with 404.

- [ ] **Step 3: Implement input-to-capability mapping**

```python
CAPABILITY_BY_INPUT = {
    "seed": McpCapability.KEYWORD_EXPAND,
    "asin": McpCapability.ASIN_KEYWORD_REVERSE,
    "category": McpCapability.CATEGORY_KEYWORDS,
}
```

Normalize whitespace and case, validate ASIN with `^[A-Z0-9]{10}$`, and reject empty inputs. Preserve returned display keyword while using normalized keyword for uniqueness.

- [ ] **Step 4: Implement source snapshots and partial status**

Persist one `SourceSnapshot` per MCP call after redacting credentials. If some enabled sources fail and at least one succeeds, save successful rows and mark run `partial`; if all fail, mark `failed` and return no keyword rows.

- [ ] **Step 5: Implement project ownership and idempotency**

Every endpoint calls `get_owned_project(project_id, current_user.username)`. Store the request id on the run or in metadata and return the existing result for repeated identical keys.

- [ ] **Step 6: Run keyword API tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_selection_api.py -k "project or keyword or snapshot" -q`

Expected: all selected tests PASS.

- [ ] **Step 7: Review checkpoint**

Verify another user receives 404 for the project and cannot retrieve source snapshots.

---

### Task 6: 实现产品方向聚合与固定评分

**Files:**
- Create: `app/selection/direction_service.py`
- Create: `app/selection/scoring.py`
- Modify: `app/routes/selection.py`
- Test: `tests/test_selection_scoring.py`
- Test: `tests/test_selection_api.py`

**Interfaces:**
- Consumes: selected `ResearchKeyword` records and competitor/trend MCP capabilities.
- Produces: `ProductDirectionService.build(project_id: int, user_id: str) -> ProductDirection`.
- Produces: `score_direction(metrics: DirectionMetrics) -> ScoreResult`.

- [ ] **Step 1: Write failing scoring tests**

```python
def test_fixed_weights_and_decision_thresholds():
    result = score_direction(DirectionMetrics(
        demand=85, competition=65, profit=88, trend=80,
        differentiation=67, quality=80, coverage=1.0,
    ))
    assert result.total == 78
    assert result.decision == "recommended"
    assert result.weights == {"demand": 20, "competition": 20, "profit": 25,
                              "trend": 10, "differentiation": 15, "quality": 10}

def test_low_coverage_blocks_recommendation():
    result = score_direction(DirectionMetrics(
        demand=100, competition=100, profit=100, trend=100,
        differentiation=100, quality=69, coverage=0.69,
    ))
    assert result.decision == "needs_data"
```

- [ ] **Step 2: Verify tests fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_selection_scoring.py -q`

Expected: FAIL because scoring module does not exist.

- [ ] **Step 3: Implement deterministic component scoring**

Use percentile normalization over comparable records. Positive components use percentile; competition components use `100 - percentile`. Omit explicitly unsupported components from the dimension average while reducing coverage. If all components of a dimension are absent, mark it unscorable.

- [ ] **Step 4: Implement keyword grouping and compatible aggregation**

Group selected words into primary, related, long-tail and scenario buckets using deterministic token overlap and MCP relevance fields. Aggregate only metrics with matching period and unit; otherwise retain separate series and add a warning.

- [ ] **Step 5: Fetch competitor and trend capabilities**

Call `COMPETITOR_SEARCH`, `COMPETITOR_METRICS`, and `KEYWORD_TREND` for the selected cluster. Preserve per-record lineage and source conflicts. Do not estimate monthly sales from reviews.

- [ ] **Step 6: Add and test product-direction API**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_selection_scoring.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_selection_api.py -k "product_direction" -q
```

Expected: tests PASS; incomplete data returns explicit warnings.

- [ ] **Step 7: Review checkpoint**

Search for hidden fixed market data: `rg -n "42000|12000|29\.99|monthly_sales_estimate|sqrt" app/selection`. Expected: no sample market values or review-to-sales estimates.

---

### Task 7: 实现运费模板、汇率与项目定价 API

**Files:**
- Modify: `app/routes/selection.py`
- Modify: `app/selection/repository.py`
- Test: `tests/test_selection_api.py`

**Interfaces:**
- Consumes: Task 2 pricing functions and `McpCapability.EXCHANGE_RATE`.
- Produces: freight template CRUD, exchange refresh, project pricing PUT/GET.

- [ ] **Step 1: Write failing API test**

```python
def test_pricing_saves_freight_and_exchange_snapshots(client_as_user, project, freight_template):
    response = client_as_user.put(f"/api/selection/projects/{project.id}/pricing", json={
        "product_price": "30", "domestic_shipping": "0", "source_currency": "CNY",
        "actual_weight_kg": "0.42", "length_cm": "18", "width_cm": "9", "height_cm": "6",
        "freight_template_id": freight_template.id,
        "commission_rate": "0.15", "target_net_margin": "0.40",
    })
    assert response.status_code == 200
    assert response.json()["freight_template_snapshot"]["id"] == freight_template.id
    assert response.json()["exchange_rate_snapshot"]["source_name"]
```

- [ ] **Step 2: Verify test fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_selection_api.py -k "freight or exchange or pricing" -q`

Expected: FAIL with 404.

- [ ] **Step 3: Implement freight template CRUD**

Require admin for create/update and authenticated users for list. Validate that fields required by `pricing_mode` are present and non-negative.

- [ ] **Step 4: Implement automatic exchange with manual override**

Call the highest-priority `EXCHANGE_RATE` source. If `manual_exchange_rate` is present, use it only for the project and mark the snapshot `manual_override: true`. If currencies match, use rate 1 with source `same_currency`.

- [ ] **Step 5: Save immutable calculation snapshots**

Persist full freight rule, rate source/time, inputs, intermediate weights, shipping, target price, commission and net profit. Updating templates or exchange rates must not mutate prior snapshots.

- [ ] **Step 6: Run API and pricing tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_selection_pricing.py tests/test_selection_api.py -k "pricing or freight or exchange" -q`

Expected: all selected tests PASS.

- [ ] **Step 7: Review checkpoint**

Verify response decimal formatting is stable and uses target currency precision.

---

### Task 8: 实现决策报告与真实 LLM 解读

**Files:**
- Create: `app/selection/report_service.py`
- Modify: `app/routes/selection.py`
- Modify: `app/main.py`
- Modify: `app/agents/product_research_agent.py`
- Test: `tests/test_selection_report.py`
- Test: `tests/test_product_research_agent.py`

**Interfaces:**
- Consumes: `ProductDirection`, `PricingSnapshot`, `ScoreResult`, existing `LLMClient`.
- Produces: `ReportService.generate(project_id: int, user_id: str) -> SelectionReport`.

- [ ] **Step 1: Write failing LLM boundary tests**

```python
def test_report_uses_rule_score_and_real_llm_text(fake_llm, complete_project):
    report = ReportService(repo=complete_project.repo, llm_client=fake_llm).generate(
        complete_project.id, "alice"
    )
    assert report.score_total == complete_project.rule_score.total
    assert report.llm_status == "succeeded"
    assert "78" in fake_llm.prompts[0][1]

def test_missing_llm_does_not_create_fallback_report(complete_project):
    report = ReportService(repo=complete_project.repo, llm_client=None).generate(
        complete_project.id, "alice"
    )
    assert report.llm_status == "unavailable"
    assert report.llm_report is None
```

- [ ] **Step 2: Verify tests fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_selection_report.py -q`

Expected: FAIL because report service does not exist.

- [ ] **Step 3: Implement structured prompt and parser**

Send only project metrics, source summaries, fixed score, pricing, risks and missing fields. Require JSON with `summary`, `findings`, `risks`, and `actions`; never ask the LLM to recompute scores or invent missing values.

- [ ] **Step 4: Implement failure status without fixed fallback**

Catch provider errors into `llm_status="failed"` and a redacted error summary. Keep `llm_report=None`. The API returns rule score and evidence alongside the failure status.

- [ ] **Step 5: Make chat ProductResearchAgent provider-neutral**

Replace “卖家精灵 MCP” fixed headings with source names returned by the registry. Include raw snapshot references and do not produce actions when research failed.

- [ ] **Step 6: Run report and agent tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_selection_report.py tests/test_product_research_agent.py -q`

Expected: tests PASS and no static production fallback is exercised.

- [ ] **Step 7: Review checkpoint**

Run `rg -n "固定|需要更多数据|建议优化定价|score.*70" app/selection app/agents/product_research_agent.py`. Remove any production fallback values.

---

### Task 9: 重建四阶段前端工作台

**Files:**
- Create: `app/static/selection-workbench.js`
- Create: `app/static/selection-workbench.css`
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: all `/api/selection/*` endpoints.
- Produces: `window.SelectionWorkbench.init()` and route page `#ai-selection`.

- [ ] **Step 1: Add failing static contract assertions**

```python
def test_selection_workbench_assets_and_stages_are_served(client):
    html = client.get("/").text
    assert "/static/selection-workbench.js" in html
    assert "/static/selection-workbench.css" in html
    assert 'data-selection-stage="keywords"' in html
    assert 'data-selection-stage="direction"' in html
    assert 'data-selection-stage="pricing"' in html
    assert 'data-selection-stage="report"' in html
    assert "Chrome 插件采集商品" not in html
```

- [ ] **Step 2: Verify test fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api.py -k "selection_workbench" -q`

Expected: FAIL because independent assets and new markup do not exist.

- [ ] **Step 3: Replace old AI selection markup**

Build project list plus project workspace with shared header, MCP status and four stage buttons. First stage contains input-type tabs, site/category inputs, filterable table and sticky research list. Other stages follow the approved visual design.

- [ ] **Step 4: Implement one explicit client state object**

```javascript
const selectionState = {
  projects: [], currentProject: null, currentStage: "keywords",
  keywordRows: [], selectedKeywordIds: new Set(), direction: null,
  pricing: null, report: null,
};
```

Use delegated event handlers and `requestJson`; do not attach inline `onclick` strings containing user data.

- [ ] **Step 5: Implement source-aware tables and errors**

Render only fields returned by the API. Use “数据源未提供” for `null`, show source/time per row, and provide a raw snapshot action. Display `partial`, capability unavailable, LLM unavailable, stale downstream stage and retry states distinctly.

- [ ] **Step 6: Implement pricing UI**

Bind product cost, domestic shipping, weight, dimensions, freight template, automatic/manual exchange, commission and fixed 40% net margin. Display formula inputs and result breakdown returned by the API; do not duplicate financial calculations in JavaScript.

- [ ] **Step 7: Remove old selection JavaScript and CSS**

Delete `selectedProducts`, `loadChromeProducts`, `analyzeSelectedProducts`, `renderProductResearchMcpData`, old Chrome buttons, raw-JSON-only panel, and their styles. Keep unrelated app functions untouched.

- [ ] **Step 8: Verify frontend**

```powershell
node --check app\static\app.js
node --check app\static\selection-workbench.js
.\.venv\Scripts\python.exe -m pytest tests/test_api.py -k "selection or frontend_static" -q
```

Expected: syntax checks exit 0 and selected tests PASS.

- [ ] **Step 9: Review checkpoint**

Open `http://localhost:8010/#ai-selection` and manually verify project creation, all stages, responsive table overflow, sticky research list, missing data and failed-source states.

---

### Task 10: 清理旧链路并执行端到端回归

**Files:**
- Modify: `app/main.py`
- Modify: `app/routes/analysis.py`
- Delete if unreferenced: `app/routes/chrome.py`
- Delete: `app/agents/product_research_mcp.py`
- Delete: `app/analysis/product_research.py`
- Modify: `tests/test_api.py`
- Modify/Delete: `tests/test_product_research.py`
- Modify: `tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: all new selection services and routes.
- Produces: one production selection path with no Chrome or seller-specific API contract.

- [ ] **Step 1: Prove consumers before deletion**

Run:

```powershell
rg -n "routes\.chrome|/api/chrome|ProductResearchMCPService|ProductResearchAnalyzer|/selection/research" app tests
```

Expected: only known legacy registrations/tests and migration targets appear. If an unrelated confirmed consumer appears, update it to the new API before deleting its dependency.

- [ ] **Step 2: Write legacy-removal assertions**

```python
def test_legacy_selection_and_chrome_routes_are_removed(client):
    assert client.post("/api/selection/research", json={"keyword": "fan"}).status_code == 404
    assert client.get("/api/chrome/products").status_code == 404
    assert client.post("/api/chrome/analyze", json={"asins": []}).status_code == 404
```

- [ ] **Step 3: Remove old route registration and files**

Remove `chrome_router` import/include from `app/main.py`, remove old selection endpoint and globals from `app/routes/analysis.py`, and delete legacy files only after Step 1 succeeds. Do not delete historical database rows.

- [ ] **Step 4: Update tests to the new source-neutral contract**

Replace `source == "sellersprite_mcp"` assertions with stable source identifiers/names supplied by fixtures. Remove tests that validate rule-generated market values from missing data.

- [ ] **Step 5: Run focused suite**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_selection_repository.py tests/test_selection_pricing.py tests/test_selection_scoring.py tests/test_selection_mcp.py tests/test_selection_api.py tests/test_selection_report.py tests/test_product_research_agent.py tests/test_mcp_tools.py -q
```

Expected: all focused tests PASS.

- [ ] **Step 6: Run full verification**

```powershell
.\.venv\Scripts\python.exe -m compileall app tests
.\.venv\Scripts\python.exe -m pytest -q
node --check app\static\app.js
node --check app\static\selection-workbench.js
```

Expected: compileall exits 0, full pytest passes, both JavaScript checks exit 0.

- [ ] **Step 7: Final safety scan**

```powershell
rg -n "StaticLLMClient|score.: 70|需要更多数据|建议优化定价|sellersprite_mcp|Chrome 插件采集商品" app
git diff --check
git status --short
```

Expected: `StaticLLMClient` appears only in explicit test injection code; legacy fixed values and UI text are absent from production selection paths; no whitespace errors. Report unrelated dirty files without modifying them.

- [ ] **Step 8: Final review checkpoint**

Provide the user with changed files, migrations, test results, known external requirements (real MCP capability mappings, credentials, exchange source and real LLM) and the manual acceptance URL. Do not stage, commit or push.
