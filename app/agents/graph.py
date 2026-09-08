from __future__ import annotations

from collections.abc import Callable

from langgraph.graph import END, StateGraph

from app.agents.llm import LLMClient
from app.agents.parser import parse_agent_response
from app.agents.types import AgentResult, OpsGraphState

SALES_ALERTS = {"sales_drop", "sales_declining_3d"}
ADS_ALERTS = {"acos_high", "clicks_without_orders", "ad_spend_increasing_without_orders_growth"}
INVENTORY_ALERTS = {"inventory_below_safety", "inventory_below_replenishment"}


def build_ops_graph(
    *,
    llm_client: LLMClient,
    feishu_sync: Callable[[OpsGraphState], str],
):
    graph = StateGraph(OpsGraphState)
    graph.add_node("load_context", _load_context)
    graph.add_node("route_alert", _route_alert)
    graph.add_node("sales_agent", _agent_node("sales_agent", llm_client))
    graph.add_node("ads_agent", _agent_node("ads_agent", llm_client))
    graph.add_node("inventory_agent", _agent_node("inventory_agent", llm_client))
    graph.add_node("summarize_recommendation", _summarize_recommendation)
    graph.add_node("sync_to_feishu", _sync_node(feishu_sync))

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "route_alert")
    graph.add_conditional_edges(
        "route_alert",
        _route_name,
        {
            "sales_agent": "sales_agent",
            "ads_agent": "ads_agent",
            "inventory_agent": "inventory_agent",
        },
    )
    graph.add_edge("sales_agent", "summarize_recommendation")
    graph.add_edge("ads_agent", "summarize_recommendation")
    graph.add_edge("inventory_agent", "summarize_recommendation")
    graph.add_edge("summarize_recommendation", "sync_to_feishu")
    graph.add_edge("sync_to_feishu", END)
    return graph.compile()


def _load_context(state: OpsGraphState) -> dict:
    return {"errors": state.get("errors", [])}


def _route_alert(state: OpsGraphState) -> dict:
    return {}


def _route_name(state: OpsGraphState) -> str:
    alert_type = state["alert_type"]
    if alert_type in SALES_ALERTS:
        return "sales_agent"
    if alert_type in ADS_ALERTS:
        return "ads_agent"
    if alert_type in INVENTORY_ALERTS:
        return "inventory_agent"
    return "sales_agent"


def _agent_node(agent_name: str, llm_client: LLMClient):
    def run(state: OpsGraphState) -> dict:
        prompt = (
            f"SKU: {state['sku']}\n"
            f"异常类型: {state['alert_type']}\n"
            f"严重程度: {state['severity']}\n"
            f"规则上下文: {state.get('rule_context', {})}\n"
            f"指标: {state['metrics']}\n"
            f"历史: {state['history']}"
        )
        try:
            llm_text = llm_client.generate(_system_prompt(agent_name), prompt)
        except Exception:
            llm_text = ""
        parsed = parse_agent_response(
            llm_text,
            severity=state["severity"],
        )
        result = AgentResult(
            agent_name=agent_name,
            abnormal=True,
            summary=parsed["summary"],
            root_causes=parsed["root_causes"],
            possible_causes=parsed["possible_causes"],
            diagnostic_checks=parsed["diagnostic_checks"],
            recommended_actions=parsed["recommended_actions"],
            priority=parsed["priority"],
            immediate_action_required=parsed["immediate_action_required"],
            severity=state["severity"] if state["severity"] in {"low", "medium", "high"} else "medium",
        )
        return {"agent_result": result.model_dump()}

    return run


def _summarize_recommendation(state: OpsGraphState) -> dict:
    if state.get("agent_result"):
        return {}
    return {
        "agent_result": AgentResult(
            agent_name="fallback_agent",
            abnormal=True,
            summary="Agent 未生成真实分析结果。",
            root_causes=[],
            possible_causes=[],
            diagnostic_checks=[],
            recommended_actions=[],
            priority=2,
            immediate_action_required=False,
            severity="medium",
        ).model_dump()
    }


def _sync_node(feishu_sync: Callable[[OpsGraphState], str]):
    def run(state: OpsGraphState) -> dict:
        try:
            status = feishu_sync(state)
            return {"feishu_sync_status": status}
        except Exception as exc:  # pragma: no cover - defensive sync boundary
            return {"feishu_sync_status": "failed", "errors": state.get("errors", []) + [str(exc)]}

    return run


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
    return (
        f"你是亚马逊运营 {agent_name}。只返回 JSON，不要 Markdown，不要解释。"
        "字段必须为：summary(最多60字), root_causes(最多3条), "
        "diagnostic_checks(最多4条), recommended_actions(最多4条), "
        "priority(1/2/3), immediate_action_required(boolean)。"
    )


def _priority(severity: str) -> int:
    return {"high": 1, "medium": 2, "low": 3}.get(severity, 2)
