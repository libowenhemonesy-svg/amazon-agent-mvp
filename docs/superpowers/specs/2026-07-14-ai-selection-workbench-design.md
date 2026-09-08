# AI 选品工作台重设计规格

## 1. 背景与目标

现有 AI 选品页面将关键词调研、卖家精灵 MCP 原始 JSON、Chrome 插件商品池和批量 AI 分析混在同一页面，数据契约与卖家精灵名称写死，无法稳定扩展其他 MCP，也无法保存完整选品项目。

本次重设计将 AI 选品改造成项目制、四阶段的选品工作台：

1. 关键词调研；
2. 产品方向研究；
3. 成本与定价；
4. 决策报告。

卖家精灵 MCP 是首个数据源，后续 MCP 必须通过统一适配层接入。系统必须保留数据来源和原始响应，固定规则负责计算，真实 LLM 仅负责解释与建议。

## 2. 已确认的产品决策

- 采用流程式工作台布局，而不是独立工具入口网格。
- 调研入口支持种子关键词、竞品 ASIN 和类目三种模式。
- 关键词结果支持指标筛选、排序、多选和加入研究清单。
- 多个已选关键词合并为一个产品方向研究。
- 研究清单、原始数据和后续结果保存为选品项目。
- AI 选品模块彻底移除 Chrome 商品池和 Chrome 批量 AI 分析，只接受 MCP 数据源。
- 多 MCP 接入采用统一能力与字段适配层。
- 净利润目标固定解释为“最终售价净利润占 40%”。
- 平台佣金默认 15%，计算时允许项目覆盖。
- 使用运费模板；汇率由外部 API 或 MCP 自动更新并允许项目内手动覆盖。
- 评分维度和权重固定，不提供管理端修改入口。
- 最终报告同时给出 0–100 分和“推荐开发 / 谨慎测试 / 暂不建议”。

## 3. 范围

### 3.1 本次包含

- 全新 AI 选品前端工作台和项目列表。
- 选品项目及四阶段数据持久化。
- 多 MCP 数据源配置、能力发现、优先级和适配器。
- 关键词调研、筛选、选择和多关键词合并。
- 产品方向的竞品、趋势、竞争与数据质量分析。
- 运费模板、汇率、成本和定价计算。
- 固定可解释评分和真实 LLM 报告。
- 原始 MCP 响应、工具名称、请求参数、时间和字段来源追溯。
- 相关 API、数据库迁移和测试。

### 3.2 本次不包含

- 广告投放、Listing 生成、图片生成、专利和合规查询。
- 实时爬取 Amazon 全站。
- 在缺少真实 MCP、汇率、成本或 LLM 数据时生成模拟结果。
- 删除数据库中历史 `SkuMaster` 数据；仅移除 AI 选品对 Chrome 数据链路的依赖和入口。

## 4. 用户流程与前端结构

### 4.1 项目入口

AI 选品导航进入项目列表。用户可新建、继续、搜索和归档项目。项目卡片展示名称、站点、当前阶段、最近更新时间、数据源状态和最终结论。

新建项目至少填写：

- 项目名称；
- Amazon 站点；
- 默认目标币种（由站点自动确定，可覆盖）。

### 4.2 工作台公共结构

项目页顶部展示项目名称、站点、更新时间、自动保存状态、MCP 连接状态和“全部项目”入口。

主区域固定展示四阶段导航：

```text
关键词调研 → 产品方向 → 成本与定价 → 决策报告
```

后续阶段依赖前置数据。用户可以返回已完成阶段修改，修改后将下游结果标记为“需要重新计算”，不静默复用旧结论。

### 4.3 第一阶段：关键词调研

输入方式以标签切换：

- 种子词：输入一个关键词；
- ASIN：输入并校验单个 Amazon ASIN；
- 类目：输入或选择 Node ID / 类目。

公共参数为站点和可选类目。系统根据当前启用 MCP 的能力声明决定入口是否可用。

结果使用表格展示。统一字段包括：

- 关键词；
- 搜索量；
- 趋势与时间范围；
- 商品数；
- 竞争度；
- CPC；
- 转化率；
- 相关度；
- 机会分；
- 数据来源与采集时间。

字段不存在时显示“数据源未提供”，不能补估算值。表格支持列设置、筛选、排序、分页、导出、查看字段来源和查看脱敏原始响应。

用户可多选关键词加入右侧研究清单。研究清单自动保存到项目。

### 4.4 第二阶段：产品方向研究

系统将已选关键词进行标准化、去重和聚类，分为：

- 主关键词；
- 核心相关词；
- 长尾机会词；
- 场景或人群词。

系统通过 MCP 获取相应竞品和市场数据，展示：

- 合并搜索量及其统计口径；
- 搜索趋势；
- 竞争强度；
- 竞品价格带；
- 竞品销量、评论和关键词覆盖（仅当数据源提供）；
- 数据完整度与数据冲突；
- 差异化机会和主要风险证据。

每个聚合指标必须能展开查看字段来源。不同时间范围或统计口径的数据不能直接相加，必须先转换为同一口径；无法转换时分别展示。

### 4.5 第三阶段：成本与定价

用户输入：

- 商品价格及币种；
- 国内运费；
- 实际重量（kg）；
- 长、宽、高（cm）；
- 运费模板；
- 平台佣金，默认 15%；
- 净利润率，默认并固定目标为 40%；
- 自动汇率或人工覆盖汇率。

运费模板支持两种计价模式：

1. 每公斤单价；
2. 首重 + 续重。

模板字段包括站点、国家、渠道、币种、最低计费重量、首重、首重价格、续重单位、续重价格、每公斤价格、体积重除数、生效日期和备注。体积重除数默认 6000。

计算公式：

```text
产品成本 C = 商品价格 + 国内运费
体积重 = 长(cm) × 宽(cm) × 高(cm) ÷ 6000
计费重量 W = max(实际重量, 体积重, 最低计费重量)
```

每公斤模式：

```text
国际运费 F = W × 每公斤价格
```

首重续重模式：

```text
W <= 首重时：F = 首重价格
W > 首重时：F = 首重价格 + ceil((W - 首重) / 续重单位) × 续重价格
```

所有成本先通过项目汇率转换为目标售价币种。设平台佣金率为 `r`、目标净利润率为 `m`，则：

```text
售价 P = (产品成本 C + 国际运费 F) ÷ (1 - r - m)
```

默认 `r = 0.15`、`m = 0.40`，因此：

```text
P = (C + F) ÷ 0.45
```

要求 `0 <= r < 1`、`0 <= m < 1` 且 `r + m < 1`。页面同时展示成本、国际运费、平台佣金、净利润和建议最低售价。

汇率自动值保存来源和更新时间。人工覆盖只影响当前项目，并明确标记。运费模板和汇率均保存项目快照，后续模板更新不改写历史计算。

### 4.6 第四阶段：决策报告

规则引擎按固定权重计算：

| 维度 | 权重 |
|---|---:|
| 市场需求 | 20 |
| 竞争强度 | 20 |
| 利润空间 | 25 |
| 搜索趋势 | 10 |
| 差异化机会 | 15 |
| 数据完整度与风险 | 10 |

各维度输出 0–100 的子分，综合分为：

```text
综合分 = Σ(维度子分 × 维度权重) ÷ 100
```

子分必须由规则引擎确定性计算。评分组件如下：

- 市场需求：合并搜索量占 60%，竞品月销量占 40%；
- 竞争强度：商品数量占 25%，竞品平均评论数占 30%，头部集中度占 25%，数据源竞争指数占 20%，均按“越低越有利”反向计分；
- 利润空间：建议售价与竞品价格带的兼容度占 50%，单位净利润占 30%，成本上浮 10% 后仍能保持的利润空间占 20%；
- 搜索趋势：标准化趋势斜率占 70%，连续增长月份占 30%；
- 差异化机会：长尾词需求占 50%，竞品关键词覆盖缺口占 50%；
- 数据完整度与风险：必需字段覆盖率占 50%，数据新鲜度占 30%，多来源一致性占 20%。

数值指标以当前 MCP 返回的可比候选池做 0–100 百分位标准化，正向指标使用百分位，负向指标使用 `100 - 百分位`。价格带兼容度以建议售价落在竞品价格四分位区间内为满分，偏离区间后按偏离比例线性扣分。某个组件的数据源明确未提供时，该组件不参与该维度的加权平均，但必须降低数据覆盖率；维度所有组件均缺失时该维度不可评分。不得用 LLM 或固定示例值补齐组件。

固定结论区间：

- 75–100：推荐开发；
- 55–74：谨慎测试；
- 0–54：暂不建议。

数据覆盖率低于 70% 时，即使综合分达到 75，也不得输出“推荐开发”，改为“需要补充数据”。缺失字段不得由 LLM 推测。

报告展示：

- 综合评分和固定结论；
- 六个维度得分；
- 每项得分的输入指标和来源；
- 风险与数据缺口；
- 定价结果；
- 真实 LLM 生成的解释和可执行建议；
- MCP 原始数据入口。

LLM 不参与数值计算和固定结论判定。LLM 不可用时保留结构化评分和证据，报告区显示真实错误和重试入口，不提供固定替代文案。

## 5. MCP 数据源架构

### 5.1 分层

```text
前端工作台
  → 选品项目服务
  → 调研流程编排器
  → 统一能力接口
  → MCP 数据源适配器
  → MCP 客户端
```

前端和评分引擎不得依赖卖家精灵专属字段或工具名称。

### 5.2 统一能力

第一版定义以下能力标识：

- `keyword_expand`：种子词扩展；
- `asin_keyword_reverse`：ASIN 关键词反查；
- `category_keywords`：类目查词；
- `keyword_metrics`：关键词指标；
- `keyword_trend`：关键词趋势；
- `competitor_search`：竞品查询；
- `competitor_metrics`：竞品指标；
- `exchange_rate`：汇率查询。

每个 MCP 数据源配置声明支持能力、对应工具、参数映射、字段映射、优先级、启用状态和超时。

### 5.3 统一适配器输出

适配器返回统一封装：

```json
{
  "source_id": "source identifier",
  "source_name": "source display name",
  "capability": "keyword_expand",
  "tool_name": "actual MCP tool",
  "collected_at": "ISO timestamp",
  "status": "succeeded | partial | failed",
  "records": [],
  "warnings": [],
  "raw_snapshot_id": "snapshot identifier"
}
```

`records` 采用能力对应的标准模型。所有标准字段允许空值，但必须同时维护字段级来源和原始字段路径。

### 5.4 多数据源合并

- 按能力选择已启用且优先级最高的数据源作为主来源。
- 可并行调用其他同能力数据源用于补充或核对。
- 同一字段冲突时保留全部值，主表显示优先级最高且口径兼容的值。
- 不同统计口径和时间范围的数据不强行合并。
- 页面明确显示主来源、其他来源、采集时间和冲突状态。
- 任一数据源失败不覆盖其他成功数据；全部失败时该能力失败。

### 5.5 密钥与原始数据

数据源非敏感配置包括名称、URL、传输方式、能力映射、优先级和启用状态。密钥、Token 和认证头仅由服务端凭据层读取，API 不返回明文，也不进入日志、错误详情或原始快照。

原始快照保存脱敏后的请求参数和响应。体积过大时允许压缩存储，但对用户展示时必须保留字段名、时间、ASIN、关键词、排名、销量、价格等业务关键字段，并明确截断状态。

## 6. 数据模型

### 6.1 `SelectionProject`

- `id`
- `name`
- `user_id`
- `marketplace`
- `target_currency`
- `status`
- `current_stage`
- `created_at`
- `updated_at`

### 6.2 `McpDataSource`

- `id`
- `name`
- `url`
- `transport`
- `enabled`
- `priority`
- `capability_config_json`
- `credential_reference`
- `created_at`
- `updated_at`

### 6.3 `KeywordResearchRun`

- `id`
- `project_id`
- `input_type`
- `input_value`
- `marketplace`
- `category`
- `filters_json`
- `status`
- `error_summary`
- `started_at`
- `completed_at`

### 6.4 `ResearchKeyword`

- `id`
- `project_id`
- `run_id`
- `keyword`
- `normalized_keyword`
- `search_volume`
- `trend_rate`
- `trend_period`
- `product_count`
- `competition_index`
- `cpc`
- `conversion_rate`
- `relevance_score`
- `opportunity_score`
- `metrics_json`（扩展字段）
- `field_lineage_json`
- `selected`
- `created_at`

项目内同一次运行以 `(run_id, normalized_keyword)` 唯一。

### 6.5 `ProductDirection`

- `id`
- `project_id`
- `name`
- `keyword_cluster_json`
- `market_metrics_json`
- `competitors_json`
- `field_lineage_json`
- `data_completeness`
- `created_at`
- `updated_at`

### 6.6 `FreightTemplate`

- `id`
- `name`
- `marketplace`
- `country`
- `channel`
- `currency`
- `pricing_mode`
- `minimum_billable_weight_kg`
- `first_weight_kg`
- `first_weight_fee`
- `additional_weight_unit_kg`
- `additional_weight_fee`
- `per_kg_rate`
- `volume_divisor`
- `effective_from`
- `enabled`
- `notes`

### 6.7 `ExchangeRate`

- `id`
- `base_currency`
- `quote_currency`
- `rate`
- `source_name`
- `source_type`
- `collected_at`

### 6.8 `PricingSnapshot`

- `id`
- `project_id`
- `product_price`
- `domestic_shipping`
- `source_currency`
- `actual_weight_kg`
- `length_cm`
- `width_cm`
- `height_cm`
- `commission_rate`
- `target_net_margin`
- `freight_template_snapshot_json`
- `exchange_rate_snapshot_json`
- `volumetric_weight_kg`
- `billable_weight_kg`
- `international_shipping`
- `target_price`
- `commission_amount`
- `net_profit_amount`
- `calculated_at`

### 6.9 `SelectionReport`

- `id`
- `project_id`
- `score_total`
- `score_dimensions_json`
- `decision`
- `evidence_json`
- `risks_json`
- `llm_status`
- `llm_report`
- `generated_at`

### 6.10 `SourceSnapshot`

- `id`
- `project_id`
- `research_run_id`
- `source_id`
- `capability`
- `tool_name`
- `request_json_redacted`
- `response_json_redacted`
- `truncated`
- `collected_at`

生产数据库结构通过 Alembic migration 管理；SQLite 开发环境保持兼容。

## 7. API 设计

```text
POST   /api/selection/projects
GET    /api/selection/projects
GET    /api/selection/projects/{project_id}
PATCH  /api/selection/projects/{project_id}

POST   /api/selection/projects/{project_id}/keyword-research
GET    /api/selection/projects/{project_id}/keyword-runs
GET    /api/selection/projects/{project_id}/keywords
PUT    /api/selection/projects/{project_id}/selected-keywords

POST   /api/selection/projects/{project_id}/product-direction
GET    /api/selection/projects/{project_id}/product-direction

PUT    /api/selection/projects/{project_id}/pricing
GET    /api/selection/projects/{project_id}/pricing

POST   /api/selection/projects/{project_id}/report
GET    /api/selection/projects/{project_id}/report

GET    /api/selection/source-snapshots/{snapshot_id}

POST   /api/selection/freight-templates
GET    /api/selection/freight-templates
PATCH  /api/selection/freight-templates/{template_id}

GET    /api/selection/exchange-rates
POST   /api/selection/exchange-rates/refresh
```

MCP 数据源管理接口继续位于设置域，但升级为多记录 CRUD。接口返回能力与连接状态，不返回凭据明文。

所有阶段写接口接收客户端请求标识，实现幂等。项目所有权在服务端校验，不能仅依赖前端隐藏。

## 8. 状态与错误处理

研究运行状态：

- `pending`
- `running`
- `succeeded`
- `partial`
- `failed`

规则：

- 未启用 MCP 时禁用调研并引导到设置页。
- MCP 不支持某能力时禁用对应入口。
- 单源失败时保留其他成功来源并标记 `partial`。
- 全部来源失败时不创建关键词结果、评分或 AI 报告。
- 原始响应解析失败时保存脱敏错误摘要和响应快照。
- 下游依赖数据改变时标记为需要重新计算。
- LLM 失败不影响结构化计算，但不产生替代报告。
- 定价参数无效时返回字段级错误，不执行计算。
- 项目阶段写入使用事务，避免只保存一半数据。

## 9. 旧功能处理

从 AI 选品模块移除：

- Chrome 商品池表格；
- 刷新、勾选、批量删除商品；
- `/api/chrome/analyze` 批量 AI 分析链路；
- 固定 70 分及固定建议等 JSON 解析失败兜底；
- 前端 `loadChromeProducts`、`analyzeSelectedProducts` 等选品依赖；
- 旧 `/api/selection/research` 的卖家精灵专属原始 JSON 页面契约。

如果 `app/routes/chrome.py` 在仓库中没有其他已确认消费者，实施时移除该路由注册和文件；若仍有独立消费者，只移除与 AI 选品相关的路由和页面依赖。不得自动删除历史数据库行。

旧 `ProductResearchAnalyzer` 不继续作为生产兜底。可复用的纯计算逻辑必须迁入新的明确服务并以真实输入为前提；无法证明仍被需要的旧逻辑在测试覆盖后移除。

## 10. 测试与验收

### 10.1 单元测试

- MCP 能力发现和参数映射；
- 不同 MCP 响应结构的标准化；
- 字段来源、冲突和优先级；
- 关键词标准化、去重和聚类；
- 运费两种计价模式；
- 体积重、计费重量和汇率转换；
- 净利润率 40%、佣金 15% 的售价公式；
- 六维固定评分和结论区间；
- 数据覆盖率低于 70% 时限制推荐。

### 10.2 API 测试

- 项目 CRUD 和所有权；
- 四阶段完整流程与自动保存；
- 幂等写入；
- MCP 未配置、部分失败和全部失败；
- 原始数据快照脱敏；
- LLM 未配置和调用失败；
- 运费模板和汇率覆盖。

### 10.3 前端验证

- 项目列表和阶段导航；
- 三种调研入口能力状态；
- 表格筛选、排序、分页、多选和研究清单；
- 数据来源、采集时间、缺失字段和冲突展示；
- 修改上游数据后下游失效提示；
- 定价字段校验和分项结果；
- 固定评分、证据与 LLM 错误状态；
- 不再显示 Chrome 商品池和 Chrome AI 分析入口。

### 10.4 验收标准

- 卖家精灵 MCP 可以作为第一个适配器完成真实关键词研究。
- 新增第二个 MCP 时无需改动前端数据模型和评分代码。
- 用户可以保存项目并从任意已完成阶段继续。
- 多个关键词可以合并为一个产品方向。
- 所有展示指标可追溯到 MCP、用户输入或明确公式。
- 缺少真实数据或服务失败时系统明确报错，不输出模拟结果。
- 定价公式和固定评分通过测试。
- 旧 Chrome 选品链路从新工作台完全消失。

## 11. 实施边界

实施应按数据库与领域模型、MCP 适配层、业务服务、API、前端四阶段工作台、旧链路清理和验证的顺序分批完成。每批只修改当前阶段必要文件，保留用户已有的无关本地改动，不修改 `.env`，不提交或推送 Git，除非用户另行明确授权。
