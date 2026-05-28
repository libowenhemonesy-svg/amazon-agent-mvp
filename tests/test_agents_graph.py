from app.agents.graph import build_ops_graph
from app.agents.llm import StaticLLMClient


def test_ops_graph_routes_sales_alert_to_sales_agent_and_syncs_feishu():
    synced = []
    graph = build_ops_graph(
        llm_client=StaticLLMClient(
            """
            {
              "summary": "销量低于7日均值，需要排查流量和转化",
              "root_causes": ["广告曝光下降", "价格或优惠变化"],
              "diagnostic_checks": ["检查曝光", "检查价格"],
              "recommended_actions": ["检查广告活动", "检查优惠券"],
              "priority": 1,
              "immediate_action_required": true
            }
            """
        ),
        feishu_sync=lambda state: synced.append(state) or "synced",
    )

    result = graph.invoke(
        {
            "run_date": "2026-01-01",
            "alert_id": 1,
            "sku": "SKU-001",
            "alert_type": "sales_drop",
            "severity": "high",
            "metrics": {"units_sold": 4, "avg_units_7d": 10},
            "history": [],
            "rule_context": {"reason": "昨日销量低于 7 日均值 50%"},
            "agent_result": {},
            "feishu_sync_status": "",
            "errors": [],
        }
    )

    assert result["agent_result"]["agent_name"] == "sales_agent"
    assert result["agent_result"]["summary"] == "销量低于7日均值，需要排查流量和转化"
    assert result["agent_result"]["root_causes"] == ["广告曝光下降", "价格或优惠变化"]
    assert result["agent_result"]["possible_causes"] == ["广告曝光下降", "价格或优惠变化"]
    assert result["agent_result"]["priority"] == 1
    assert result["agent_result"]["diagnostic_checks"]
    assert result["agent_result"]["immediate_action_required"] is True
    assert result["feishu_sync_status"] == "synced"
    assert synced[0]["sku"] == "SKU-001"


def test_ops_graph_routes_ads_and_inventory_alerts_to_matching_agents():
    graph = build_ops_graph(
        llm_client=StaticLLMClient("建议动作：检查投放或补货计划。"),
        feishu_sync=lambda state: "synced",
    )

    ads_result = graph.invoke(
        {
            "run_date": "2026-01-01",
            "alert_id": 2,
            "sku": "SKU-002",
            "alert_type": "acos_high",
            "severity": "medium",
            "metrics": {},
            "history": [],
            "rule_context": {},
            "agent_result": {},
            "feishu_sync_status": "",
            "errors": [],
        }
    )
    inventory_result = graph.invoke(
        {
            "run_date": "2026-01-01",
            "alert_id": 3,
            "sku": "SKU-003",
            "alert_type": "inventory_below_safety",
            "severity": "high",
            "metrics": {},
            "history": [],
            "rule_context": {},
            "agent_result": {},
            "feishu_sync_status": "",
            "errors": [],
        }
    )

    assert ads_result["agent_result"]["agent_name"] == "ads_agent"
    assert inventory_result["agent_result"]["agent_name"] == "inventory_agent"


def test_ops_graph_does_not_store_long_markdown_llm_text_in_summary():
    graph = build_ops_graph(
        llm_client=StaticLLMClient("# 分析报告\n\n" + "很长的解释。" * 200),
        feishu_sync=lambda state: "synced",
    )

    result = graph.invoke(
        {
            "run_date": "2026-01-01",
            "alert_id": 4,
            "sku": "SKU-004",
            "alert_type": "inventory_below_replenishment",
            "severity": "high",
            "metrics": {},
            "history": [],
            "rule_context": {},
            "agent_result": {},
            "feishu_sync_status": "",
            "errors": [],
        }
    )

    assert len(result["agent_result"]["summary"]) <= 60
    assert "# 分析报告" not in result["agent_result"]["summary"]


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
