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
    assert agent_result["summary"] == "Agent 未返回可解析的真实分析结果。"
    assert agent_result["root_causes"] == []
    assert agent_result["diagnostic_checks"] == []
    assert agent_result["recommended_actions"] == []


def test_sales_agent_declining_trend_fallback_does_not_use_drop_ratio_context():
    graph = build_ops_graph(
        llm_client=StaticLLMClient("# 很长的销售分析\n\n" + "无法解析。" * 100),
        feishu_sync=lambda state: "synced",
    )

    result = graph.invoke(
        {
            "run_date": "2026-01-07",
            "alert_id": 12,
            "sku": "SKU-001",
            "alert_type": "sales_declining_3d",
            "severity": "medium",
            "metrics": {
                "units_sold": 4,
                "avg_units_7d": 7,
                "sales_trend_7d": [10, 9, 8, 7, 6, 5, 4],
            },
            "history": [],
            "rule_context": {
                "observed": [6, 5, 4],
                "baseline": "3-day trend",
                "threshold": "strictly declining",
                "unit": "units",
            },
            "agent_result": {},
            "feishu_sync_status": "",
            "errors": [],
        }
    )

    assert result["agent_result"]["summary"] == "Agent 未返回可解析的真实分析结果。"
    assert result["agent_result"]["priority"] == 2


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
    assert agent_result["summary"] == "Agent 未返回可解析的真实分析结果。"
    assert agent_result["root_causes"] == []
    assert agent_result["diagnostic_checks"] == []
    assert agent_result["recommended_actions"] == []
