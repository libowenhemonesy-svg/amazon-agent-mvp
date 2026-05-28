# Ads Analysis Agent Design

## Scope

This spec covers the second agent only: the Ads Analysis Agent.

The system continues to use rule detection plus agent analysis. Rules decide whether a SKU has an advertising problem. The agent explains the problem, lists likely causes, and generates concrete advertising optimization actions.

The agent does not decide whether an alert should exist. It only analyzes an alert that has already been created by the rule engine.

## Role

The Ads Analysis Agent monitors SKU-level advertising efficiency and explains advertising waste or conversion problems.

Primary responsibilities:

- Monitor ACOS, ROAS, CTR, CVR, CPC, advertising spend, clicks, ad orders, and ad sales.
- Identify high-spend low-conversion advertising patterns.
- Identify clicks without orders.
- Identify rising spend that does not produce order growth.
- Generate practical advertising optimization suggestions.

Out of scope for this agent:

- Inventory replenishment decisions.
- Profit and margin accounting.
- Sales trend diagnosis outside advertising impact.
- Overall daily business summary.

The agent may mention Listing conversion quality as a possible advertising conversion cause, but it should not perform deep Listing content diagnosis in this phase.

## Alert Types

The initial Ads Analysis Agent supports three advertising alert types:

1. `acos_high`
2. `clicks_without_orders`
3. `ad_spend_increasing_without_orders_growth`

Existing alert types stay in place:

- `acos_high`: ACOS is more than 10 percentage points above target ACOS.
- `clicks_without_orders`: clicks are at or above the threshold, but advertising orders are zero.

The new trend alert is:

- `ad_spend_increasing_without_orders_growth`: recent advertising spend is increasing, but advertising orders are not growing with it.

## Detection Rules

### ACOS High

Trigger `acos_high` when:

- `target_acos > 0`
- And `acos > target_acos + 0.1`

Severity:

- `medium`

Rule context:

- `observed`: current ACOS.
- `baseline`: target ACOS.
- `threshold`: `target_acos + 0.1`.
- `unit`: `ratio`.

### Clicks Without Orders

Trigger `clicks_without_orders` when:

- `clicks >= 20`
- And `ad_orders == 0`

Severity:

- `medium`

Rule context:

- `observed`: clicks.
- `baseline`: ad orders.
- `threshold`: `20`.
- `unit`: `clicks`.

### Spend Increasing Without Order Growth

Trigger `ad_spend_increasing_without_orders_growth` using the last three entries in `ads_trend_7d`.

Required conditions:

- The last three spend values are strictly increasing.
- The last day's order count is less than or equal to the first day's order count.
- The last day's spend is greater than `0`.

Example:

```json
[
  {"date": "2026-01-05", "spend": 30, "orders": 2, "acos": 0.35},
  {"date": "2026-01-06", "spend": 45, "orders": 2, "acos": 0.42},
  {"date": "2026-01-07", "spend": 72, "orders": 1, "acos": 0.55}
]
```

Severity:

- `medium`

Rule context:

- `observed`: last three spend and order values.
- `baseline`: first day spend and first day orders.
- `threshold`: `spend strictly increasing and orders not increasing`.
- `unit`: `mixed`.

This rule intentionally does not require ACOS to exceed target ACOS. ACOS may be missing or temporarily unreliable when ad sales are zero, but the spend/order trend is still useful.

## Inputs

The rule engine and agent graph should provide the Ads Analysis Agent with these fields:

- `sku`
- `alert_type`
- `severity`
- `impressions`
- `clicks`
- `spend`
- `ad_orders`
- `ad_sales`
- `ctr`
- `cvr`
- `cpc`
- `acos`
- `roas`
- `target_acos`
- `ads_trend_7d`
- `rule_context`
- `history`

## Output Contract

The agent must return compact JSON that fits the existing `AgentResult` shape:

```json
{
  "agent_name": "ads_agent",
  "abnormal": true,
  "summary": "近 3 日广告花费持续增加，但广告订单未同步增长，ACOS 高于目标值。",
  "root_causes": ["关键词匹配过宽", "无效点击增加", "转化率下降"],
  "possible_causes": ["关键词匹配过宽", "无效点击增加", "转化率下降", "Listing 页面转化不足"],
  "diagnostic_checks": ["检查高花费搜索词", "检查点击无订单关键词", "检查 CTR/CVR 是否低于历史", "检查广告组 ACOS"],
  "recommended_actions": ["降低低转化关键词出价", "否定无效搜索词", "保留有订单且 ACOS 可控的广告组"],
  "priority": 2,
  "immediate_action_required": false,
  "severity": "medium"
}
```

Field requirements:

- `summary` must mention the matched advertising rule and at least one key metric.
- `root_causes` should contain up to 3 likely causes.
- `possible_causes` should contain up to 5 possible causes.
- `diagnostic_checks` should contain concrete advertising checks.
- `recommended_actions` should contain direct optimization actions.
- `priority` is `2` for initial medium-severity advertising alerts.
- `immediate_action_required` is `false` for initial medium-severity advertising alerts.

## Prompt Boundary

The Ads Analysis Agent system prompt should define the role and prevent domain drift:

```text
你是亚马逊广告分析 Agent。
你的任务是基于 ACOS、ROAS、CTR、CVR、CPC、广告花费、点击、广告订单和广告趋势，解释广告效率异常。
只分析广告投放问题，不分析库存补货、利润核算或整体经营日报。
只返回紧凑 JSON，不要 Markdown，不要解释。
字段必须为：summary(最多60字), root_causes(最多3条), diagnostic_checks(最多5条), recommended_actions(最多4条), priority(1/2/3), immediate_action_required(boolean)。
异常说明必须结合命中的广告规则和关键指标。
可能原因优先从关键词匹配过宽、无效点击增加、转化率下降、Listing 页面转化不足中选择。
建议动作必须具体到广告优化动作。
```

The user prompt should include the SKU, alert type, severity, rule context, metrics, and recent history.

## Fallback Behavior

If the LLM returns malformed JSON, Markdown, or overly long prose, the parser should use deterministic fallback content.

For `acos_high`:

```text
ACOS 高于目标值，需检查广告花费、转化率和低效广告组。
```

For `clicks_without_orders`:

```text
点击达到阈值但无广告订单，需排查搜索词质量和 Listing 转化。
```

For `ad_spend_increasing_without_orders_growth`:

```text
近 3 日广告花费持续增加，但广告订单未同步增长，需优化低转化投放。
```

Fallback causes:

- 关键词匹配过宽
- 无效点击增加
- 转化率下降
- Listing 页面转化不足

Fallback checks:

- 检查高花费搜索词
- 检查点击无订单关键词
- 检查 CTR/CVR 是否低于历史
- 检查广告组 ACOS

Fallback actions:

- 降低低转化关键词出价
- 否定无效搜索词
- 保留有订单且 ACOS 可控的广告组

## Data Flow

1. Daily metrics are calculated for each SKU.
2. The rule engine evaluates advertising rules.
3. An advertising alert is created when a rule is met.
4. The agent graph routes advertising alert types to `ads_agent`.
5. `ads_agent` receives metrics and rule context.
6. The LLM generates compact JSON analysis.
7. The parser validates and normalizes the result.
8. The alert stores the structured agent result.
9. Feishu sync and the dashboard display the task-card output.

## Testing

Focused tests should cover:

- `acos_high` still triggers when ACOS exceeds target ACOS by more than 10 percentage points.
- `clicks_without_orders` still triggers when clicks are at least 20 and ad orders are zero.
- `ad_spend_increasing_without_orders_growth` triggers when the last three spend values increase and orders do not grow.
- The new trend alert does not trigger when spend increases but orders also increase.
- All three advertising alert types route to `ads_agent`.
- The Ads Analysis Agent prompt includes ACOS, ROAS, CTR, CVR, CPC, spend, clicks, orders, and trend responsibilities.
- Malformed LLM output falls back to compact advertising recommendations.

## Acceptance Criteria

The Ads Analysis Agent is complete when:

- Advertising problems are detected by rules, not by the LLM.
- Existing `acos_high` and `clicks_without_orders` behavior continues to work.
- The new spend/order trend rule is deterministic and covered by tests.
- The agent explains advertising alerts using structured JSON.
- The task-card output matches the user's example in tone and content.
- Existing agent parsing and Feishu/dashboard flows continue to work.
