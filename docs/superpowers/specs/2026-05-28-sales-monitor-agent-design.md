# Sales Monitor Agent Design

## Scope

This spec covers the first agent only: the Sales Monitor Agent.

The initial system will use rule detection plus agent analysis. Rules decide whether a SKU has a sales problem. The agent explains the problem, lists likely causes, and generates concrete follow-up actions.

The agent does not decide whether an alert should exist. It only analyzes an alert that has already been created by the rule engine.

## Role

The Sales Monitor Agent monitors SKU-level sales performance and explains sales drops.

Primary responsibilities:

- Monitor daily SKU units sold and sales amount.
- Compare daily units sold with 7-day, 14-day, and 30-day average units.
- Explain obvious sales drops in concise business language.
- Generate likely cause checks for operations staff.
- Recommend concrete next actions.

Out of scope for this agent:

- Advertising efficiency diagnosis such as ACOS, CPC, CTR, or ROAS optimization.
- Inventory replenishment decisions.
- Profit and margin diagnosis.
- Overall daily business summary.

The agent may mention advertising traffic, price, coupons, inventory state, and competitor promotion as possible causes, but it should not perform deep analysis for those domains.

## Detection Rule

The first implementation uses the fixed sales-drop rule selected by the user:

- If `avg_units_7d > 0`
- And `units_sold < avg_units_7d * 0.5`
- Then create a `sales_drop` alert.

The alert severity is `high` for the initial MVP.

The decline ratio is:

```text
(avg_units_7d - units_sold) / avg_units_7d
```

Example:

```text
units_sold = 5
avg_units_7d = 12
decline_ratio = 58%
```

Low-volume suppression, lifecycle-specific thresholds, and multi-level severity can be added later, but they are not part of this first agent design.

## Inputs

The rule engine and agent graph should provide the Sales Monitor Agent with these fields:

- `sku`
- `alert_type`
- `severity`
- `units_sold`
- `sales_amount`
- `avg_units_7d`
- `avg_units_14d`
- `avg_units_30d`
- `sales_trend_7d`
- `rule_context`
- `history`

`rule_context` should include:

- `observed`: yesterday's units sold.
- `baseline`: 7-day average units sold.
- `threshold`: 50% of the 7-day average units sold.
- `unit`: `units`.
- `decline_ratio`: percentage decline versus the 7-day average.

## Output Contract

The agent must return compact JSON that fits the existing `AgentResult` shape:

```json
{
  "agent_name": "sales_agent",
  "abnormal": true,
  "summary": "昨日销量为 5 单，低于近 7 日平均销量 12 单，下降幅度为 58%。",
  "root_causes": ["广告流量下降", "价格变化", "优惠活动结束"],
  "possible_causes": ["广告流量下降", "价格变化", "优惠活动结束", "库存状态异常", "竞品促销"],
  "diagnostic_checks": ["检查广告曝光", "检查购物车状态", "检查优惠券状态", "检查库存状态", "检查主要竞品价格"],
  "recommended_actions": ["优先检查广告曝光、购物车状态、优惠券状态、库存状态和主要竞品价格变化"],
  "priority": 1,
  "immediate_action_required": true,
  "severity": "high"
}
```

Field requirements:

- `summary` must mention yesterday's units sold, the 7-day average, and the decline percentage.
- `root_causes` should contain up to 3 likely causes.
- `possible_causes` should contain up to 5 possible causes.
- `diagnostic_checks` should contain concrete checks, not generic advice.
- `recommended_actions` should be short enough for a task card.
- `priority` is `1` for the initial high-severity sales drop.
- `immediate_action_required` is `true` for the initial high-severity sales drop.

## Prompt Boundary

The Sales Monitor Agent system prompt should define the role and prevent domain drift:

```text
你是亚马逊销售监控 Agent。
你的任务是基于 SKU 的日销量、销售额、7日/14日/30日均销量和近期趋势，解释销售异常的业务含义。
只分析销售下滑，不分析广告投产、库存补货或利润问题。
只返回紧凑 JSON，不要 Markdown，不要解释。
异常说明必须包含昨日销量、近7日均销量和下降幅度。
可能原因优先从广告流量下降、价格变化、优惠活动结束、库存状态异常、竞品促销中选择。
建议动作必须具体到可检查项。
```

The user prompt should include the SKU, alert type, severity, rule context, metrics, and recent history.

## Fallback Behavior

If the LLM returns malformed JSON, Markdown, or overly long prose, the parser should keep using the existing fallback path and produce a short task-card response.

The Sales Monitor Agent fallback summary should be deterministic and include the core sales-drop numbers when metrics are available:

```text
昨日销量低于近 7 日平均销量 50%，需排查流量、价格、优惠、库存和竞品变化。
```

Fallback actions:

- Check advertising exposure.
- Check Buy Box or shopping-cart state.
- Check coupon or promotion status.
- Check inventory availability.
- Check main competitor price or promotion changes.

## Data Flow

1. Daily metrics are calculated for each SKU.
2. The rule engine evaluates the fixed sales-drop rule.
3. A `sales_drop` alert is created when the rule is met.
4. The agent graph routes `sales_drop` to `sales_agent`.
5. `sales_agent` receives metrics and rule context.
6. The LLM generates a compact JSON analysis.
7. The parser validates and normalizes the result.
8. The alert stores the structured agent result.
9. Feishu sync and the dashboard display the task-card output.

## Testing

Focused tests should cover:

- A SKU with `units_sold = 5` and `avg_units_7d = 12` creates a `sales_drop` alert.
- The sales alert includes `observed`, `baseline`, `threshold`, and `decline_ratio` in `rule_context`.
- `sales_drop` routes to `sales_agent`.
- The Sales Monitor Agent output summary includes yesterday's units, 7-day average, and decline percentage.
- Malformed LLM output falls back to a compact deterministic recommendation.

## Acceptance Criteria

The first Sales Monitor Agent is complete when:

- Sales drops are detected by rule, not by the LLM.
- The fixed rule matches the user's selected threshold: yesterday's units below 50% of the 7-day average.
- The agent explains the alert using structured JSON.
- The task-card output matches the user's example in tone and content.
- Existing agent parsing and Feishu/dashboard flows continue to work.
