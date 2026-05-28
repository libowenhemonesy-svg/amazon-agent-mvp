# Ads Analysis Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Ads Analysis Agent using rule detection plus agent analysis for ACOS, clicks-without-orders, and rising-spend-without-order-growth advertising alerts.

**Architecture:** The rule engine detects advertising alerts deterministically and emits structured `rule_context`. The LangGraph agent layer routes all advertising alert types to `ads_agent`, which uses an ads-specific prompt and deterministic fallback task-card content when LLM output is invalid.

**Tech Stack:** Python 3.11, FastAPI app modules, LangGraph, Pydantic, pytest.

---

## File Structure

- Modify `app/rules/engine.py`: add the `ad_spend_increasing_without_orders_growth` rule based on the last three `ads_trend_7d` entries.
- Modify `app/agents/graph.py`: route the new alert type to `ads_agent`; add an ads-specific prompt and alert-aware fallback summaries.
- Modify `tests/test_rules.py`: add trend-rule coverage and preserve current `acos_high` / `clicks_without_orders` tests.
- Modify `tests/test_agents_graph.py`: verify the new alert routes to `ads_agent`, the ads prompt is role-specific, and malformed LLM output gets advertising fallback content.

No new runtime module is needed. The existing metrics already expose `impressions`, `clicks`, `spend`, `ad_orders`, `ad_sales`, `ctr`, `cvr`, `cpc`, `acos`, `roas`, `target_acos`, and `ads_trend_7d`.

---

### Task 1: Advertising Trend Rule

**Files:**
- Modify: `app/rules/engine.py`
- Test: `tests/test_rules.py`

- [ ] **Step 1: Write failing tests for the new trend rule**

Append these tests to `tests/test_rules.py`:

```python
def test_evaluate_alert_rules_detects_ad_spend_increasing_without_orders_growth():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-ADS",
                "units_sold": 10,
                "avg_units_7d": 10,
                "three_day_sales_decline": False,
                "acos": 0.35,
                "target_acos": 0.3,
                "clicks": 12,
                "ad_orders": 1,
                "inventory_days": 60,
                "safety_stock_days": 30,
                "replenishment_days": 20,
                "ads_trend_7d": [
                    {"date": "2026-01-01", "spend": 10, "orders": 2, "acos": 0.25},
                    {"date": "2026-01-02", "spend": 12, "orders": 3, "acos": 0.27},
                    {"date": "2026-01-03", "spend": 14, "orders": 2, "acos": 0.3},
                    {"date": "2026-01-04", "spend": 16, "orders": 2, "acos": 0.32},
                    {"date": "2026-01-05", "spend": 30, "orders": 2, "acos": 0.35},
                    {"date": "2026-01-06", "spend": 45, "orders": 2, "acos": 0.42},
                    {"date": "2026-01-07", "spend": 72, "orders": 1, "acos": 0.55},
                ],
            }
        ]
    )

    trend_alert = next(
        alert for alert in alerts if alert["alert_type"] == "ad_spend_increasing_without_orders_growth"
    )
    assert trend_alert["severity"] == "medium"
    assert trend_alert["reason"] == "近 3 日广告花费持续增加，但广告订单未同步增长"
    assert trend_alert["rule_context"]["observed"] == {
        "spend": [30, 45, 72],
        "orders": [2, 2, 1],
    }
    assert trend_alert["rule_context"]["baseline"] == {
        "spend": 30,
        "orders": 2,
    }
    assert trend_alert["rule_context"]["threshold"] == "spend strictly increasing and orders not increasing"
    assert trend_alert["rule_context"]["unit"] == "mixed"


def test_evaluate_alert_rules_does_not_emit_ad_trend_alert_when_orders_grow_with_spend():
    alerts = evaluate_alert_rules(
        [
            {
                "sku": "SKU-ADS-OK",
                "units_sold": 10,
                "avg_units_7d": 10,
                "three_day_sales_decline": False,
                "acos": 0.25,
                "target_acos": 0.3,
                "clicks": 12,
                "ad_orders": 4,
                "inventory_days": 60,
                "safety_stock_days": 30,
                "replenishment_days": 20,
                "ads_trend_7d": [
                    {"date": "2026-01-05", "spend": 30, "orders": 1, "acos": 0.35},
                    {"date": "2026-01-06", "spend": 45, "orders": 2, "acos": 0.32},
                    {"date": "2026-01-07", "spend": 72, "orders": 4, "acos": 0.28},
                ],
            }
        ]
    )

    assert not [
        alert for alert in alerts if alert["alert_type"] == "ad_spend_increasing_without_orders_growth"
    ]
```

- [ ] **Step 2: Run the new rule tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rules.py::test_evaluate_alert_rules_detects_ad_spend_increasing_without_orders_growth tests/test_rules.py::test_evaluate_alert_rules_does_not_emit_ad_trend_alert_when_orders_grow_with_spend -q
```

Expected: the first test fails because `ad_spend_increasing_without_orders_growth` is not emitted yet.

- [ ] **Step 3: Implement the new rule**

In `app/rules/engine.py`, add this block after the existing `clicks_without_orders` block:

```python
        ad_trend = row.get("ads_trend_7d", [])[-3:]
        if _spend_increasing_without_orders_growth(ad_trend):
            spend_values = [entry.get("spend", 0) for entry in ad_trend]
            order_values = [entry.get("orders", 0) for entry in ad_trend]
            alerts.append(
                _alert(
                    date_value,
                    sku,
                    "ad_spend_increasing_without_orders_growth",
                    "medium",
                    "近 3 日广告花费持续增加，但广告订单未同步增长",
                    observed={
                        "spend": spend_values,
                        "orders": order_values,
                    },
                    baseline={
                        "spend": spend_values[0],
                        "orders": order_values[0],
                    },
                    threshold="spend strictly increasing and orders not increasing",
                    unit="mixed",
                )
            )
```

Add this helper above `_alert`:

```python
def _spend_increasing_without_orders_growth(ad_trend: list[dict[str, Any]]) -> bool:
    if len(ad_trend) < 3:
        return False
    spend_values = [float(entry.get("spend", 0) or 0) for entry in ad_trend]
    order_values = [int(entry.get("orders", 0) or 0) for entry in ad_trend]
    spend_increasing = spend_values[0] < spend_values[1] < spend_values[2]
    orders_not_growing = order_values[-1] <= order_values[0]
    return spend_values[-1] > 0 and spend_increasing and orders_not_growing
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
git commit -m "Add advertising spend trend rule"
```

---

### Task 2: Ads Agent Routing, Prompt, And Fallback

**Files:**
- Modify: `app/agents/graph.py`
- Test: `tests/test_agents_graph.py`

- [ ] **Step 1: Write failing agent tests**

Append these tests to `tests/test_agents_graph.py`:

```python
def test_ops_graph_routes_ad_spend_trend_alert_to_ads_agent():
    graph = build_ops_graph(
        llm_client=StaticLLMClient(
            """
            {
              "summary": "近 3 日广告花费持续增加，但广告订单未同步增长",
              "root_causes": ["关键词匹配过宽", "无效点击增加"],
              "diagnostic_checks": ["检查高花费搜索词", "检查广告组 ACOS"],
              "recommended_actions": ["降低低转化关键词出价", "否定无效搜索词"],
              "priority": 2,
              "immediate_action_required": false
            }
            """
        ),
        feishu_sync=lambda state: "synced",
    )

    result = graph.invoke(
        {
            "run_date": "2026-01-07",
            "alert_id": 20,
            "sku": "SKU-ADS",
            "alert_type": "ad_spend_increasing_without_orders_growth",
            "severity": "medium",
            "metrics": {
                "spend": 72,
                "ad_orders": 1,
                "ad_sales": 130,
                "acos": 0.55,
                "target_acos": 0.3,
                "roas": 1.8,
                "ctr": 0.03,
                "cvr": 0.015,
                "cpc": 1.1,
                "clicks": 65,
                "impressions": 2200,
                "ads_trend_7d": [
                    {"date": "2026-01-05", "spend": 30, "orders": 2, "acos": 0.35},
                    {"date": "2026-01-06", "spend": 45, "orders": 2, "acos": 0.42},
                    {"date": "2026-01-07", "spend": 72, "orders": 1, "acos": 0.55},
                ],
            },
            "history": [],
            "rule_context": {
                "observed": {"spend": [30, 45, 72], "orders": [2, 2, 1]},
                "baseline": {"spend": 30, "orders": 2},
                "threshold": "spend strictly increasing and orders not increasing",
                "unit": "mixed",
            },
            "agent_result": {},
            "feishu_sync_status": "",
            "errors": [],
        }
    )

    assert result["agent_result"]["agent_name"] == "ads_agent"
    assert result["agent_result"]["summary"] == "近 3 日广告花费持续增加，但广告订单未同步增长"


def test_ads_agent_receives_ads_analysis_prompt():
    prompts = []

    class RecordingLLM:
        def generate(self, system_prompt: str, user_prompt: str) -> str:
            prompts.append((system_prompt, user_prompt))
            return """
            {
              "summary": "ACOS 高于目标值，需检查广告花费和转化率",
              "root_causes": ["关键词匹配过宽", "转化率下降"],
              "diagnostic_checks": ["检查高花费搜索词", "检查广告组 ACOS"],
              "recommended_actions": ["降低低转化关键词出价", "保留有订单且 ACOS 可控的广告组"],
              "priority": 2,
              "immediate_action_required": false
            }
            """

    graph = build_ops_graph(llm_client=RecordingLLM(), feishu_sync=lambda state: "synced")

    result = graph.invoke(
        {
            "run_date": "2026-01-07",
            "alert_id": 21,
            "sku": "SKU-ADS",
            "alert_type": "acos_high",
            "severity": "medium",
            "metrics": {
                "acos": 0.45,
                "target_acos": 0.3,
                "roas": 2.2,
                "ctr": 0.04,
                "cvr": 0.02,
                "cpc": 1.2,
                "spend": 72,
                "clicks": 60,
                "ad_orders": 2,
                "ads_trend_7d": [],
            },
            "history": [],
            "rule_context": {
                "observed": 0.45,
                "baseline": 0.3,
                "threshold": 0.4,
                "unit": "ratio",
            },
            "agent_result": {},
            "feishu_sync_status": "",
            "errors": [],
        }
    )

    system_prompt, user_prompt = prompts[0]
    assert "亚马逊广告分析 Agent" in system_prompt
    assert "ACOS、ROAS、CTR、CVR、CPC" in system_prompt
    assert "只分析广告投放问题" in system_prompt
    assert "异常说明必须结合命中的广告规则和关键指标" in system_prompt
    assert "target_acos" in user_prompt
    assert "roas" in user_prompt
    assert result["agent_result"]["possible_causes"] == ["关键词匹配过宽", "转化率下降"]


def test_ads_agent_malformed_output_uses_alert_specific_fallback():
    graph = build_ops_graph(
        llm_client=StaticLLMClient("# 广告分析报告\n\n" + "无法解析。" * 100),
        feishu_sync=lambda state: "synced",
    )

    result = graph.invoke(
        {
            "run_date": "2026-01-07",
            "alert_id": 22,
            "sku": "SKU-ADS",
            "alert_type": "clicks_without_orders",
            "severity": "medium",
            "metrics": {
                "clicks": 65,
                "ad_orders": 0,
                "acos": 0,
                "target_acos": 0.3,
                "roas": 0,
                "ctr": 0.03,
                "cvr": 0,
                "cpc": 1.1,
            },
            "history": [],
            "rule_context": {
                "observed": 65,
                "baseline": 0,
                "threshold": 20,
                "unit": "clicks",
            },
            "agent_result": {},
            "feishu_sync_status": "",
            "errors": [],
        }
    )

    agent_result = result["agent_result"]
    assert agent_result["agent_name"] == "ads_agent"
    assert agent_result["summary"] == "点击达到阈值但无广告订单，需排查搜索词质量和 Listing 转化。"
    assert agent_result["root_causes"] == ["关键词匹配过宽", "无效点击增加", "转化率下降", "Listing 页面转化不足"]
    assert agent_result["diagnostic_checks"] == [
        "检查高花费搜索词",
        "检查点击无订单关键词",
        "检查 CTR/CVR 是否低于历史",
        "检查广告组 ACOS",
    ]
    assert agent_result["recommended_actions"] == [
        "降低低转化关键词出价",
        "否定无效搜索词",
        "保留有订单且 ACOS 可控的广告组",
    ]
```

- [ ] **Step 2: Run the new agent tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agents_graph.py::test_ops_graph_routes_ad_spend_trend_alert_to_ads_agent tests/test_agents_graph.py::test_ads_agent_receives_ads_analysis_prompt tests/test_agents_graph.py::test_ads_agent_malformed_output_uses_alert_specific_fallback -q
```

Expected: failures for missing new route, generic ads prompt, and generic ads fallback summary.

- [ ] **Step 3: Implement routing, prompt, and fallback**

In `app/agents/graph.py`, update `ADS_ALERTS` to:

```python
ADS_ALERTS = {"acos_high", "clicks_without_orders", "ad_spend_increasing_without_orders_growth"}
```

In `_system_prompt`, add this branch before the generic return:

```python
    if agent_name == "ads_agent":
        return (
            "你是亚马逊广告分析 Agent。"
            "你的任务是基于 ACOS、ROAS、CTR、CVR、CPC、广告花费、点击、广告订单和广告趋势，解释广告效率异常。"
            "只分析广告投放问题，不分析库存补货、利润核算或整体经营日报。"
            "只返回紧凑 JSON，不要 Markdown，不要解释。"
            "字段必须为：summary(最多60字), root_causes(最多4条), "
            "diagnostic_checks(最多5条), recommended_actions(最多4条), "
            "priority(1/2/3), immediate_action_required(boolean)。"
            "异常说明必须结合命中的广告规则和关键指标。"
            "可能原因优先从关键词匹配过宽、无效点击增加、转化率下降、Listing 页面转化不足中选择。"
            "建议动作必须具体到广告优化动作。"
        )
```

Update `_fallback_summary`:

```python
    if agent_name == "ads_agent":
        return _ads_fallback_summary(state)
```

Add this helper below `_sales_fallback_summary`:

```python
def _ads_fallback_summary(state: OpsGraphState) -> str:
    alert_type = state["alert_type"]
    if alert_type == "acos_high":
        return "ACOS 高于目标值，需检查广告花费、转化率和低效广告组。"
    if alert_type == "clicks_without_orders":
        return "点击达到阈值但无广告订单，需排查搜索词质量和 Listing 转化。"
    if alert_type == "ad_spend_increasing_without_orders_growth":
        return "近 3 日广告花费持续增加，但广告订单未同步增长，需优化低转化投放。"
    return f"{alert_type} 命中，需排查广告效率"
```

Update `_default_causes`, `_default_actions`, and `_diagnostic_checks` ads branches:

```python
    if agent_name == "ads_agent":
        return ["关键词匹配过宽", "无效点击增加", "转化率下降", "Listing 页面转化不足"]
```

```python
    if agent_name == "ads_agent":
        return ["降低低转化关键词出价", "否定无效搜索词", "保留有订单且 ACOS 可控的广告组"]
```

```python
    if agent_name == "ads_agent":
        return ["检查高花费搜索词", "检查点击无订单关键词", "检查 CTR/CVR 是否低于历史", "检查广告组 ACOS"]
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
git commit -m "Implement ads analysis agent"
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

Expected: no modified tracked files from this plan remain uncommitted. Existing unrelated untracked project files may still appear because the repository started with many untracked files.

- [ ] **Step 3: Commit any missed implementation files**

If `git status --short` shows modified tracked files from this plan that were not committed, run:

```powershell
git add app/rules/engine.py app/agents/graph.py tests/test_rules.py tests/test_agents_graph.py
git commit -m "Complete ads analysis agent implementation"
```

Expected: git creates a commit only if there were missed implementation changes.

---

## Self-Review

- Spec coverage: Task 1 implements the new trend alert and preserves existing ads rules; Task 2 implements routing, ads prompt, and alert-specific fallback; Task 3 verifies the whole suite.
- Placeholder scan: No placeholder tasks remain. Every implementation step includes concrete code and exact commands.
- Type consistency: The plan uses existing `evaluate_alert_rules`, `ADS_ALERTS`, `OpsGraphState`, `build_ops_graph`, and `parse_agent_response` boundaries. The new alert type is consistently named `ad_spend_increasing_without_orders_growth`.
