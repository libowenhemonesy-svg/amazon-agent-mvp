# Sales Monitor Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first Sales Monitor Agent using rule detection plus agent analysis for fixed 50% sales-drop alerts.

**Architecture:** The rule engine owns alert detection and emits a `sales_drop` alert when yesterday's units are below 50% of the 7-day average. The LangGraph agent layer routes that alert to `sales_agent`, which produces compact structured JSON and deterministic fallback task-card content when the LLM output is invalid.

**Tech Stack:** Python 3.11, FastAPI app modules, LangGraph, Pydantic, pytest.

---

## File Structure

- Modify `app/rules/engine.py`: replace lifecycle-specific sales-drop thresholding with the selected fixed 50% rule and include `decline_ratio` in `rule_context`.
- Modify `app/agents/graph.py`: make the sales agent prompt role-specific and provide metric-aware fallback text for sales alerts.
- Modify `tests/test_rules.py`: update rule expectations for fixed 50% sales-drop behavior and `decline_ratio`.
- Modify `tests/test_agents_graph.py`: verify sales-agent output shape, routing, and deterministic fallback behavior.

No new runtime module is needed for the first agent. Keeping the change inside the existing rule engine and graph follows the current MVP structure.

---

### Task 1: Fixed Sales-Drop Rule

**Files:**
- Modify: `app/rules/engine.py`
- Test: `tests/test_rules.py`

- [ ] **Step 1: Write the failing rule tests**

Replace `tests/test_rules.py` with:

```python
from app.rules.engine import evaluate_alert_rules


def test_evaluate_alert_rules_detects_sales_drop_below_half_of_7d_average():
    metrics = [
        {
            "sku": "SKU-001",
            "units_sold": 5,
            "avg_units_7d": 12,
            "avg_units_14d": 11,
            "avg_units_30d": 10,
            "three_day_sales_decline": False,
            "sales_trend_7d": [11, 12, 13, 12, 11, 12, 5],
            "acos": 0.2,
            "target_acos": 0.3,
            "clicks": 10,
            "ad_orders": 1,
            "inventory_days": 60,
            "safety_stock_days": 30,
            "replenishment_days": 20,
        }
    ]

    alerts = evaluate_alert_rules(metrics)

    sales_drop = next(alert for alert in alerts if alert["alert_type"] == "sales_drop")
    assert sales_drop["severity"] == "high"
    assert sales_drop["reason"] == "昨日销量低于近 7 日平均销量 50%"
    assert sales_drop["rule_context"]["observed"] == 5
    assert sales_drop["rule_context"]["baseline"] == 12
    assert sales_drop["rule_context"]["threshold"] == 6
    assert sales_drop["rule_context"]["unit"] == "units"
    assert sales_drop["rule_context"]["decline_ratio"] == 0.5833


def test_evaluate_alert_rules_does_not_use_lifecycle_sales_thresholds():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-GROWTH",
                "units_sold": 55,
                "avg_units_7d": 100,
                "three_day_sales_decline": False,
                "lifecycle": "growth",
                "acos": 0,
                "target_acos": 0.3,
                "clicks": 0,
                "ad_orders": 0,
                "inventory_days": 60,
                "safety_stock_days": 30,
                "replenishment_days": 20,
            }
        ]
    )

    assert not [alert for alert in alerts if alert["alert_type"] == "sales_drop"]


def test_evaluate_alert_rules_detects_sales_ads_and_inventory_alerts():
    metrics = [
        {
            "sku": "SKU-001",
            "units_sold": 4,
            "avg_units_7d": 10,
            "three_day_sales_decline": True,
            "acos": 0.45,
            "target_acos": 0.3,
            "clicks": 30,
            "ad_orders": 0,
            "inventory_days": 15,
            "safety_stock_days": 30,
            "replenishment_days": 20,
        }
    ]

    alerts = evaluate_alert_rules(metrics)

    assert {alert["alert_type"] for alert in alerts} == {
        "sales_drop",
        "sales_declining_3d",
        "acos_high",
        "clicks_without_orders",
        "inventory_below_replenishment",
    }
    assert all(alert["sku"] == "SKU-001" for alert in alerts)
    sales_drop = next(alert for alert in alerts if alert["alert_type"] == "sales_drop")
    assert sales_drop["rule_context"]["observed"] == 4
    assert sales_drop["rule_context"]["baseline"] == 10
    assert sales_drop["rule_context"]["threshold"] == 5


def test_evaluate_alert_rules_avoids_zero_baseline_sales_false_positive():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-ZERO",
                "units_sold": 0,
                "avg_units_7d": 0,
                "three_day_sales_decline": True,
                "lifecycle": "new",
                "acos": 0,
                "target_acos": 0.3,
                "clicks": 0,
                "ad_orders": 0,
                "inventory_days": 60,
                "safety_stock_days": 30,
                "replenishment_days": 20,
            }
        ]
    )

    assert not [alert for alert in alerts if alert["alert_type"].startswith("sales")]


def test_evaluate_alert_rules_uses_custom_replenishment_days():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-INV",
                "units_sold": 10,
                "avg_units_7d": 10,
                "three_day_sales_decline": False,
                "lifecycle": "stable",
                "acos": 0.2,
                "target_acos": 0.3,
                "clicks": 5,
                "ad_orders": 1,
                "inventory_days": 24,
                "safety_stock_days": 30,
                "replenishment_days": 25,
            }
        ]
    )

    assert {alert["alert_type"] for alert in alerts} == {"inventory_below_replenishment"}
    replenishment = next(alert for alert in alerts if alert["alert_type"] == "inventory_below_replenishment")
    assert replenishment["rule_context"]["threshold"] == 25


def test_evaluate_alert_rules_emits_one_inventory_alert_per_sku_when_thresholds_overlap():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-INV",
                "units_sold": 0,
                "avg_units_7d": 0,
                "three_day_sales_decline": False,
                "lifecycle": "stable",
                "acos": 0,
                "target_acos": 0.3,
                "clicks": 0,
                "ad_orders": 0,
                "inventory_days": 0,
                "safety_stock_days": 30,
                "replenishment_days": 25,
            }
        ]
    )

    assert [alert["alert_type"] for alert in alerts] == ["inventory_below_replenishment"]


def test_evaluate_alert_rules_detects_profit_and_quality_alerts():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-PROFIT",
                "units_sold": 10,
                "avg_units_7d": 10,
                "three_day_sales_decline": False,
                "lifecycle": "stable",
                "acos": 0.2,
                "target_acos": 0.3,
                "clicks": 10,
                "ad_orders": 2,
                "inventory_days": 60,
                "safety_stock_days": 30,
                "replenishment_days": 20,
                "gross_margin": 0.22,
                "target_gross_margin": 0.35,
                "return_rate": 0.02,
                "negative_reviews": 0,
                "rating": 4.5,
            },
            {
                "sku": "SKU-QUALITY",
                "units_sold": 10,
                "avg_units_7d": 10,
                "three_day_sales_decline": False,
                "lifecycle": "stable",
                "acos": 0.2,
                "target_acos": 0.3,
                "clicks": 10,
                "ad_orders": 2,
                "inventory_days": 60,
                "safety_stock_days": 30,
                "replenishment_days": 20,
                "gross_margin": 0.45,
                "target_gross_margin": 0.35,
                "return_rate": 0.18,
                "negative_reviews": 2,
                "rating": 3.7,
            },
        ]
    )

    assert {alert["alert_type"] for alert in alerts} == {"profit_below_target", "quality_risk"}
```

- [ ] **Step 2: Run the new rule tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rules.py -q
```

Expected: at least one failure showing the current lifecycle threshold reason or missing `decline_ratio`.

- [ ] **Step 3: Implement the fixed rule**

In `app/rules/engine.py`, remove `LIFECYCLE_SALES_DROP_RATIO` and replace the current sales-drop block in `evaluate_alert_rules` with:

```python
        avg_units_7d = row.get("avg_units_7d", 0)
        units_sold = row.get("units_sold", 0)
        sales_drop_threshold = round(avg_units_7d * 0.5, 2)

        if avg_units_7d and units_sold < sales_drop_threshold:
            alerts.append(
                _alert(
                    date_value,
                    sku,
                    "sales_drop",
                    "high",
                    "昨日销量低于近 7 日平均销量 50%",
                    observed=units_sold,
                    baseline=avg_units_7d,
                    threshold=sales_drop_threshold,
                    unit="units",
                    extra_context={
                        "decline_ratio": round((avg_units_7d - units_sold) / avg_units_7d, 4),
                    },
                )
            )
```

Update `_alert` to accept and merge optional extra context:

```python
def _alert(
    date_value: Any,
    sku: str,
    alert_type: str,
    severity: str,
    reason: str,
    *,
    observed: Any,
    baseline: Any,
    threshold: Any,
    unit: str,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rule_context = {
        "observed": observed,
        "baseline": baseline,
        "threshold": threshold,
        "unit": unit,
    }
    if extra_context:
        rule_context.update(extra_context)
    return {
        "date": date_value,
        "sku": sku,
        "alert_type": alert_type,
        "severity": severity,
        "reason": reason,
        "rule_context": rule_context,
    }
```

- [ ] **Step 4: Run the rule tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rules.py -q
```

Expected: all tests in `tests/test_rules.py` pass.

- [ ] **Step 5: Commit the rule change**

Run:

```powershell
git add app/rules/engine.py tests/test_rules.py
git commit -m "Implement fixed sales drop rule"
```

---

### Task 2: Sales Agent Prompt And Fallback

**Files:**
- Modify: `app/agents/graph.py`
- Test: `tests/test_agents_graph.py`

- [ ] **Step 1: Write the failing agent tests**

Append these tests to `tests/test_agents_graph.py`:

```python
def test_sales_agent_receives_sales_monitor_prompt():
    prompts = []

    class RecordingLLM:
        def generate(self, system_prompt: str, user_prompt: str) -> str:
            prompts.append((system_prompt, user_prompt))
            return """
            {
              "summary": "昨日销量为 5 单，低于近 7 日平均销量 12 单，下降幅度为 58%。",
              "root_causes": ["广告流量下降", "价格变化", "优惠活动结束"],
              "diagnostic_checks": ["检查广告曝光", "检查购物车状态", "检查优惠券状态"],
              "recommended_actions": ["优先检查广告曝光、购物车状态、优惠券状态、库存状态和主要竞品价格变化"],
              "priority": 1,
              "immediate_action_required": true
            }
            """

    graph = build_ops_graph(llm_client=RecordingLLM(), feishu_sync=lambda state: "synced")

    result = graph.invoke(
        {
            "run_date": "2026-01-07",
            "alert_id": 10,
            "sku": "SKU-001",
            "alert_type": "sales_drop",
            "severity": "high",
            "metrics": {
                "units_sold": 5,
                "sales_amount": 120.5,
                "avg_units_7d": 12,
                "avg_units_14d": 11,
                "avg_units_30d": 10,
                "sales_trend_7d": [11, 12, 13, 12, 11, 12, 5],
            },
            "history": [],
            "rule_context": {
                "observed": 5,
                "baseline": 12,
                "threshold": 6,
                "unit": "units",
                "decline_ratio": 0.5833,
            },
            "agent_result": {},
            "feishu_sync_status": "",
            "errors": [],
        }
    )

    system_prompt, user_prompt = prompts[0]
    assert "亚马逊销售监控 Agent" in system_prompt
    assert "只分析销售下滑" in system_prompt
    assert "异常说明必须包含昨日销量、近7日均销量和下降幅度" in system_prompt
    assert "avg_units_14d" in user_prompt
    assert "avg_units_30d" in user_prompt
    assert result["agent_result"]["summary"] == "昨日销量为 5 单，低于近 7 日平均销量 12 单，下降幅度为 58%。"
    assert result["agent_result"]["possible_causes"] == ["广告流量下降", "价格变化", "优惠活动结束"]


def test_sales_agent_malformed_output_uses_metric_aware_fallback():
    graph = build_ops_graph(
        llm_client=StaticLLMClient("# 很长的销售分析\n\n" + "无法解析。" * 100),
        feishu_sync=lambda state: "synced",
    )

    result = graph.invoke(
        {
            "run_date": "2026-01-07",
            "alert_id": 11,
            "sku": "SKU-001",
            "alert_type": "sales_drop",
            "severity": "high",
            "metrics": {
                "units_sold": 5,
                "avg_units_7d": 12,
                "avg_units_14d": 11,
                "avg_units_30d": 10,
            },
            "history": [],
            "rule_context": {
                "observed": 5,
                "baseline": 12,
                "threshold": 6,
                "unit": "units",
                "decline_ratio": 0.5833,
            },
            "agent_result": {},
            "feishu_sync_status": "",
            "errors": [],
        }
    )

    agent_result = result["agent_result"]
    assert agent_result["agent_name"] == "sales_agent"
    assert agent_result["summary"] == "昨日销量为 5 单，低于近 7 日平均销量 12 单，下降幅度为 58%。"
    assert agent_result["root_causes"] == ["广告流量下降", "价格变化", "优惠活动结束"]
    assert agent_result["diagnostic_checks"] == [
        "检查广告曝光",
        "检查购物车状态",
        "检查优惠券状态",
        "检查库存状态",
        "检查主要竞品价格",
    ]
    assert agent_result["recommended_actions"] == [
        "优先检查广告曝光、购物车状态、优惠券状态、库存状态和主要竞品价格变化"
    ]
```

- [ ] **Step 2: Run the new agent tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agents_graph.py -q
```

Expected: failures for missing role-specific prompt and metric-aware fallback.

- [ ] **Step 3: Implement role-specific sales prompt and fallback**

In `app/agents/graph.py`, change the `parse_agent_response` call inside `_agent_node` to:

```python
        parsed = parse_agent_response(
            llm_text,
            fallback_summary=_fallback_summary(agent_name, state),
            severity=state["severity"],
        )
```

Change `_system_prompt` to:

```python
def _system_prompt(agent_name: str) -> str:
    if agent_name == "sales_agent":
        return (
            "你是亚马逊销售监控 Agent。"
            "你的任务是基于 SKU 的日销量、销售额、7日/14日/30日均销量和近期趋势，解释销售异常的业务含义。"
            "只分析销售下滑，不分析广告投产、库存补货或利润问题。"
            "只返回紧凑 JSON，不要 Markdown，不要解释。"
            "字段必须为：summary(最多60字), root_causes(最多3条), "
            "diagnostic_checks(最多5条), recommended_actions(最多4条), "
            "priority(1/2/3), immediate_action_required(boolean)。"
            "异常说明必须包含昨日销量、近7日均销量和下降幅度。"
            "可能原因优先从广告流量下降、价格变化、优惠活动结束、库存状态异常、竞品促销中选择。"
            "建议动作必须具体到可检查项。"
        )
    return (
        f"你是亚马逊运营 {agent_name}。只返回 JSON，不要 Markdown，不要解释。"
        "字段必须为：summary(最多60字), root_causes(最多3条), "
        "diagnostic_checks(最多4条), recommended_actions(最多4条), "
        "priority(1/2/3), immediate_action_required(boolean)。"
    )
```

Replace `_fallback_summary` with:

```python
def _fallback_summary(agent_name: str, state: OpsGraphState) -> str:
    alert_type = state["alert_type"]
    if agent_name == "sales_agent":
        return _sales_fallback_summary(state)
    if agent_name == "ads_agent":
        return f"{alert_type} 命中，需排查广告效率"
    return f"{alert_type} 命中，需排查库存和补货"
```

Add this helper below `_fallback_summary`:

```python
def _sales_fallback_summary(state: OpsGraphState) -> str:
    metrics = state.get("metrics", {})
    rule_context = state.get("rule_context", {})
    units_sold = rule_context.get("observed", metrics.get("units_sold"))
    avg_units_7d = rule_context.get("baseline", metrics.get("avg_units_7d"))
    decline_ratio = rule_context.get("decline_ratio")
    if decline_ratio is None and avg_units_7d:
        decline_ratio = round((avg_units_7d - units_sold) / avg_units_7d, 4)
    if units_sold is not None and avg_units_7d:
        decline_percent = round(float(decline_ratio or 0) * 100)
        return f"昨日销量为 {units_sold:g} 单，低于近 7 日平均销量 {avg_units_7d:g} 单，下降幅度为 {decline_percent}%。"
    return "昨日销量低于近 7 日平均销量 50%，需排查流量、价格、优惠、库存和竞品变化。"
```

Update `_default_causes`, `_default_actions`, and `_diagnostic_checks` sales branches to:

```python
    if agent_name == "sales_agent":
        return ["广告流量下降", "价格变化", "优惠活动结束"]
```

```python
    if agent_name == "sales_agent":
        return ["优先检查广告曝光、购物车状态、优惠券状态、库存状态和主要竞品价格变化"]
```

```python
    if agent_name == "sales_agent":
        return ["检查广告曝光", "检查购物车状态", "检查优惠券状态", "检查库存状态", "检查主要竞品价格"]
```

- [ ] **Step 4: Run the agent tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agents_graph.py -q
```

Expected: all tests in `tests/test_agents_graph.py` pass.

- [ ] **Step 5: Commit the agent change**

Run:

```powershell
git add app/agents/graph.py tests/test_agents_graph.py
git commit -m "Implement sales monitor agent analysis"
```

---

### Task 3: Regression Verification

**Files:**
- Verify: all changed source and test files.

- [ ] **Step 1: Run the full test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Inspect git status**

Run:

```powershell
git status --short
```

Expected: only intentional uncommitted files remain, or no output if everything relevant has been committed.

- [ ] **Step 3: Commit any missed implementation files**

If `git status --short` shows modified files from this plan that were not committed, run:

```powershell
git add app/rules/engine.py app/agents/graph.py tests/test_rules.py tests/test_agents_graph.py
git commit -m "Complete sales monitor agent implementation"
```

Expected: git creates a commit only if there were missed implementation changes.

---

## Self-Review

- Spec coverage: Task 1 implements rule detection and `decline_ratio`; Task 2 implements role prompt, structured agent analysis, and fallback behavior; Task 3 verifies the full test suite.
- Placeholders: No placeholder tasks remain. Every code step includes concrete code and exact commands.
- Type consistency: The plan uses the existing `OpsGraphState`, `AgentResult`, `evaluate_alert_rules`, `build_ops_graph`, and `parse_agent_response` boundaries.
