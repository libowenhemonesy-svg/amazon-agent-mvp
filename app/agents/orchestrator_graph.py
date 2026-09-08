from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict


class OrchestratorState(TypedDict):
    conversation_id: str
    user_message: str
    intent: str
    entities: dict[str, Any]
    route: str
    task_status: str
    agent_results: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    final_answer: str
    errors: list[str]
    research_context: dict[str, Any]


Executor = Callable[[OrchestratorState], Awaitable[dict[str, Any]] | dict[str, Any]]


INTENT_ROUTE = {
    "data_query": "chat_graph",
    "unknown": "chat_graph",
    "agent_status": "agent_status",
    "mcp_status": "mcp_status",
    "product_research": "chat_graph",
    "listing_generation": "product_listing",
    "image_generation": "product_image",
    "ops_diagnosis": "ops_diagnosis",
    "ads_optimization": "ads_optimization",
    "inventory_check": "inventory_check",
    "report_generation": "report_generation",
}


def classify_intent(message: str) -> str:
    text = message.lower()
    if _contains_any(text, ["mcp", "工具列表", "工具状态", "卖家精灵工具"]):
        return "mcp_status"
    if _contains_any(text, ["几个agent", "哪些agent", "有什么agent", "agent列表", "你有几个 agent", "你有哪些 agent"]):
        return "agent_status"
    if _contains_any(
        text,
        [
            "生图",
            "产品图",
            "主图",
            "场景图",
            "a+图",
            "详情图",
            "海报",
            "banner",
            "生成图片",
            "图片生成",
            "生成图",
        ],
    ):
        return "image_generation"
    if _contains_any(
        text,
        [
            "listing",
            "标题",
            "五点",
            "bullet",
            "description",
            "产品描述",
            "长描述",
            "search terms",
            "后台搜索词",
        ],
    ):
        return "listing_generation"
    if _contains_any(text, ["日报", "周报", "报告", "总结运营", "运营总结"]):
        return "report_generation"
    if _contains_any(text, ["选品", "能不能做", "能做吗", "关键词", "市场", "竞品"]):
        return "product_research"
    if _contains_any(text, ["acos", "广告", "投放", "关键词出价", "预算", "cpc", "roas"]):
        return "ads_optimization"
    if _contains_any(text, ["库存", "补货", "断货", "可售", "在途", "周转"]):
        return "inventory_check"
    if _contains_any(text, ["为什么", "原因", "诊断", "异常", "下滑", "下降", "掉了", "变差"]):
        return "ops_diagnosis"
    if _contains_any(text, ["查", "查询", "看一下", "最近", "销量", "销售", "利润", "退货", "sku"]):
        return "data_query"
    return "unknown"


def extract_entities(message: str) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    sku_match = re.search(r"\bSKU[-_\w]*\b", message, flags=re.IGNORECASE)
    if sku_match:
        entities["sku"] = sku_match.group(0).upper()

    asin_match = re.search(r"\bB0[A-Z0-9]{8}\b", message, flags=re.IGNORECASE)
    if asin_match:
        entities["asin"] = asin_match.group(0).upper()

    days_match = re.search(r"最近\s*(\d+)\s*天", message)
    if days_match:
        entities["days"] = int(days_match.group(1))

    keyword = _extract_keyword(message)
    if keyword:
        entities["keyword"] = keyword

    return entities


class OrchestratorGraph:
    """总调度 Agent：分类、路由、执行专业能力，并统一汇总回复。"""

    def __init__(
        self,
        *,
        chat_graph,
        executors: dict[str, Executor] | None = None,
    ) -> None:
        self.chat_graph = chat_graph
        self.executors = executors or {}
        self.last_state: OrchestratorState | None = None
        self._conversation_research_context: dict[str, dict[str, Any]] = {}
        self._conversation_listing_context: dict[str, dict[str, Any]] = {}

    async def chat(self, message: str, conversation_id: str = "default") -> str:
        chunks = []
        async for event in self.chat_stream(message, conversation_id):
            if event.get("type") == "token":
                chunks.append(event.get("content", ""))
        return "".join(chunks)

    async def chat_stream(self, message: str, conversation_id: str = "default"):
        state = self._new_state(message, conversation_id)
        self.last_state = state
        self._hydrate_listing_generation_context(state)
        self._hydrate_image_generation_context(state)

        if state["intent"] == "mcp_status":
            state["task_status"] = "completed"
            mcp_context = await self._build_mcp_context()
            # 让 AI 根据 MCP 真实状态组织回复
            prompted = (
                f"用户问：{message}\n\n"
                f"以下是当前 MCP 接入情况的真实数据，请根据这些信息用自然语言回复用户：\n"
                f"{mcp_context}"
            )
            async for event in self.chat_graph.chat_stream(prompted, conversation_id):
                yield event
            yield {"type": "done", "conversation_id": conversation_id}
            return

        if state["intent"] == "listing_generation" and not state["entities"].get("keyword"):
            state["task_status"] = "failed"
            state["final_answer"] = "请先提供关键词或先做选品研究，再让我根据关键词生成 Listing 文案。"
            yield {"type": "token", "content": state["final_answer"]}
            yield {"type": "done", "conversation_id": conversation_id}
            return

        if state["intent"] == "image_generation" and not state["entities"].get("keyword"):
            state["task_status"] = "failed"
            state["final_answer"] = "请先提供关键词或先做选品研究，再让我根据关键词生成产品图。"
            yield {"type": "token", "content": state["final_answer"]}
            yield {"type": "done", "conversation_id": conversation_id}
            return

        if state["route"] == "chat_graph" or state["route"] not in self.executors:
            async for event in self.chat_graph.chat_stream(message, conversation_id):
                yield event
            state["task_status"] = "completed"
            return

        yield {"type": "tool_start", "tool": f"orchestrator:{state['route']}", "args": state["entities"]}
        try:
            result = await self._run_executor(state)
        except Exception as exc:
            state["task_status"] = "failed"
            state["errors"].append(str(exc))
            yield {"type": "error", "content": f"总调度执行失败: {exc}"}
            yield {"type": "done", "conversation_id": conversation_id}
            return

        state["agent_results"].append(result)
        self._remember_agent_result(state, result)
        state["final_answer"] = _format_result(result)
        state["task_status"] = "completed"
        yield {"type": "tool_end", "tool": f"orchestrator:{state['route']}", "result": state["final_answer"][:200]}
        yield {"type": "token", "content": state["final_answer"]}
        if result.get("image_url"):
            yield {"type": "token", "content": f"\n图片链接：{result['image_url']}"}
            yield {
                "type": "image",
                "url": result["image_url"],
                "prompt": result.get("prompt", ""),
                "title": f"{result.get('keyword', '')} 产品图".strip(),
            }
        yield {"type": "done", "conversation_id": conversation_id}

    def _new_state(self, message: str, conversation_id: str) -> OrchestratorState:
        intent = classify_intent(message)
        route = INTENT_ROUTE.get(intent, "chat_graph")
        return {
            "conversation_id": conversation_id,
            "user_message": message,
            "intent": intent,
            "entities": extract_entities(message),
            "route": route,
            "task_status": "running",
            "agent_results": [],
            "tool_results": [],
            "final_answer": "",
            "errors": [],
            "research_context": {},
        }

    async def _run_executor(self, state: OrchestratorState) -> dict[str, Any]:
        result = self.executors[state["route"]](state)
        if inspect.isawaitable(result):
            result = await result
        return dict(result)

    async def _build_mcp_context(self) -> str:
        """构建 MCP 状态上下文，交给 AI 自由组织语言回复。"""
        status_getter = getattr(self.chat_graph, "get_mcp_status", None)
        if status_getter is None:
            return (
                "【MCP 状态】未配置\n"
                "当前系统没有接入任何 MCP 服务。"
            )
        status = status_getter()
        if inspect.isawaitable(status):
            status = await status

        if status.get("load_error"):
            return (
                f"【MCP 状态】配置但加载失败\n"
                f"错误：{status['load_error']}\n"
                f"请检查 SELLERSPRITE_MCP_URL 和 API Key 是否正确。"
            )
        if not status.get("enabled"):
            return (
                "【MCP 状态】未启用\n"
                "当前没有配置 MCP 工具加载器，请检查环境变量配置。"
            )
        if not status.get("mcp_tool_count"):
            return (
                f"【MCP 状态】已启用但无工具\n"
                f"本地工具数：{status.get('local_tool_count', 0)}\n"
                f"可能原因：MCP 服务地址不可达、API Key 无效或未配置。\n"
                f"请检查 SELLERSPRITE_MCP_URL 和 SELLERSPRITE_API_KEY。"
            )

        tool_names = "\n".join(f"- {name}" for name in status.get("mcp_tool_names", []))
        return (
            f"【MCP 状态】已连接\n"
            f"本地工具数：{status.get('local_tool_count', 0)}\n"
            f"MCP 工具数：{status.get('mcp_tool_count', 0)}\n"
            f"工具列表：\n{tool_names}"
        )

    def _hydrate_image_generation_context(self, state: OrchestratorState) -> None:
        if state["intent"] != "image_generation":
            return
        context = self._conversation_research_context.get(state["conversation_id"], {})
        listing_context = self._conversation_listing_context.get(state["conversation_id"], {})
        if listing_context:
            context = {**context, "listing": listing_context.get("listing", {})}
        state["research_context"] = context
        if not state["entities"].get("keyword") and context.get("keyword"):
            state["entities"]["keyword"] = context["keyword"]

    def _hydrate_listing_generation_context(self, state: OrchestratorState) -> None:
        if state["intent"] != "listing_generation":
            return
        context = self._conversation_research_context.get(state["conversation_id"], {})
        state["research_context"] = context
        if not state["entities"].get("keyword") and context.get("keyword"):
            state["entities"]["keyword"] = context["keyword"]

    def _remember_agent_result(self, state: OrchestratorState, result: dict[str, Any]) -> None:
        if state["intent"] == "listing_generation":
            self._conversation_listing_context[state["conversation_id"]] = {
                "keyword": result.get("keyword") or state["entities"].get("keyword", ""),
                "listing": result.get("listing") or {},
            }
            return
        if state["intent"] != "product_research":
            return
        raw = result.get("raw") or {}
        context = {
            "keyword": result.get("keyword") or raw.get("keyword") or state["entities"].get("keyword", ""),
            "raw": raw,
            "decision": raw.get("decision", {}),
            "pricing": raw.get("pricing_advice", {}),
            "competitors": raw.get("competitors", [])[:5],
        }
        self._conversation_research_context[state["conversation_id"]] = context


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _extract_keyword(message: str) -> str:
    patterns = [
        r"关键词\s*[:：]?\s*([A-Za-z0-9][A-Za-z0-9\s\-]{1,80})",
        r"keyword\s*[:：]?\s*([A-Za-z0-9][A-Za-z0-9\s\-]{1,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            keyword = match.group(1).strip()
            keyword = re.split(r"[，,。?？]", keyword, maxsplit=1)[0].strip()
            if keyword:
                return keyword
    return ""


def _format_result(result: dict[str, Any]) -> str:
    summary = str(result.get("summary") or "任务已完成。").strip()
    lines = [summary]

    evidence = result.get("evidence") or []
    if evidence:
        lines.append("")
        lines.append("【依据】")
        lines.extend(str(item) for item in evidence[:6])

    actions = result.get("actions") or result.get("recommended_actions") or []
    if actions:
        lines.append("")
        lines.append("【建议动作】")
        lines.extend(str(item) for item in actions[:6])

    return "\n".join(lines)
