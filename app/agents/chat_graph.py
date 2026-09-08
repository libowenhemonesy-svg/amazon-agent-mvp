"""LangGraph 聊天 Agent - 支持多轮对话和工具调用"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from app.agents.tools import ChatTools

# 系统提示词
CHAT_SYSTEM_PROMPT = """你是 Amazon 运营数据分析助手。你有访问卖家精灵 MCP 工具的能力。

【核心规则 — 必须遵守】
1. 当调用 sellersprite 工具后，必须基于工具返回的真实数据进行分析和回答
2. 禁止用编造的数据或训练记忆代替工具返回的真实数据
3. 如果工具返回了数据，回答时必须引用数据中的具体数字（搜索量、竞价、供需比等）
4. 如果工具返回了原始 JSON，从中提取关键数值并在分析中引用
5. 如果工具返回为空或失败，如实告知用户

【格式规则】
- 禁止使用 * 号、| 竖线、markdown 表格、emoji
- 禁止提问
- 每条数据占一行，一行内展示所有信息
- 重要内容用【】标注
- 数据和分析之间空一行

回复示例：
告警 1 SKU-001 可售天数低于补货周期 25 天 可售库存：40 在途：0 预留：0

【重点关注】SKU-001 在途库存为 0，建议尽快安排补货。
"""

# 需要过滤的思考内容关键词
THINKING_KEYWORDS = [
    "好的",
    "我来",
    "让我",
    "首先",
    "我需要",
    "我先",
    "接下来",
    "我将",
    "请问",
    "在您回复之前",
    "我来帮您",
    "查询一下",
    "获取一下",
    "看看",
    "看看有",
    "看看数据",
    "现在查询",
    "现在查看",
    "正在查询",
    "正在查看",
    "帮您查询",
    "帮您查看",
    "为您查询",
    "为您查看",
]

def filter_thinking(text: str) -> str:
    """过滤掉LLM的思考内容和不合规格式"""
    import re

    # 先移除行首的思考内容（保留后面的数据）
    for keyword in THINKING_KEYWORDS:
        # 找到关键词位置，移除关键词及其前面的内容，直到遇到数据开始
        # 例如："现在查询这些SKU的库存详情。告警 1 SKU-001" -> "告警 1 SKU-001"
        idx = text.find(keyword)
        if idx >= 0:
            # 找到关键词后的第一个句号或换行
            end_idx = idx + len(keyword)
            # 继续往后找，直到遇到句号、换行或数据开始
            while end_idx < len(text) and text[end_idx] not in '。.\n':
                end_idx += 1
            # 跳过句号
            if end_idx < len(text) and text[end_idx] in '。.':
                end_idx += 1
            # 移除思考内容
            text = text[end_idx:].lstrip()

    lines = text.split("\n")
    filtered = []
    for line in lines:
        stripped = line.strip()
        # 跳过 markdown 分隔线（---, ===, ***）
        if re.match(r'^[\-=*]{3,}$', stripped):
            continue
        # 跳过 markdown 表格分隔行（如 |:---|:---:| 或 :---: :---）
        if re.match(r'^[:\-\s|]+$', stripped):
            continue
        # 跳过 markdown 标题（### 等）
        if re.match(r'^#{1,6}\s', stripped):
            continue
        # 跳过空行（保留一个）
        if not stripped and filtered and not filtered[-1]:
            continue
        # 移除 markdown 格式符号
        line = line.replace("**", "").replace("*", "")
        line = line.replace("__", "").replace("_", "")
        # 移除 | 竖线（表格格式）
        line = line.replace("|", " ")
        # 移除 emoji
        line = re.sub(r'[\U0001F300-\U0001F9FF☀-⛿✀-➿⚠️]', '', line)
        # 清理多余的空格
        line = re.sub(r'\s+', ' ', line).strip()
        if line:
            filtered.append(line)
    # 移除开头的空行
    while filtered and not filtered[0].strip():
        filtered.pop(0)
    return "\n".join(filtered)


def _tool_name(tool_item: Any) -> str:
    return str(getattr(tool_item, "name", tool_item))


def _build_contextual_message(
    tools: list[Any],
    local_tool_count: int,
    user_message: str,
) -> str:
    """把 MCP 工具现状附到用户消息上，确保 LLM 知道该用什么工具查数据。"""
    mcp_tools = tools[local_tool_count:]
    mcp_names = [_tool_name(t) for t in mcp_tools]

    if not mcp_names:
        return user_message

    lines = [
        f"【可用数据源 — 请注意】",
        f"当前已接入卖家精灵 MCP，以下工具可以查询真实的 Amazon 市场数据。",
        f"你对任何产品/关键词/市场的分析都必须基于这些工具的返回结果，",
        f"绝对不能使用训练数据或记忆中的数据。如果没有查到数据，必须如实告诉用户。",
        f"",
    ]

    # 区分出 list_tools 和 call_tool
    if "sellersprite_mcp_list_tools" in mcp_names:
        lines.append(
            "步骤：先用 sellersprite_mcp_list_tools 看看有哪些具体工具可调用，"
            "然后用 sellersprite_mcp_call_tool 调用你需要的那一个。"
        )
    elif "sellersprite_mcp_call_tool" in mcp_names:
        lines.append(
            "用 sellersprite_mcp_call_tool 调用卖家精灵的具体工具。"
            "先调用 sellersprite_mcp_list_tools 查询可用工具列表后再使用。"
        )

    lines.append("")
    lines.append(f"用户消息：{user_message}")
    return "\n".join(lines)


def _build_memory_contextual_message(memory_context: str, user_message: str) -> str:
    """把可信记忆作为参考上下文附到用户消息前。"""
    if not memory_context.strip():
        return user_message
    return "\n".join(
        [
            "【可参考记忆】",
            memory_context.strip(),
            "",
            "注意：记忆只能作为上下文参考；涉及销量、利润、广告、库存、竞品、关键词等实时数据时，必须查询真实数据源。",
            "",
            f"用户消息：{user_message}",
        ]
    )


def _build_mcp_system_addon(tools: list[Any], local_tool_count: int) -> str:
    """生成 MCP 系统提示词附加段，让 LLM 知道必须用工具查数据。"""
    mcp_tools = tools[local_tool_count:]
    mcp_names = [_tool_name(t) for t in mcp_tools]

    if not mcp_names:
        return ""

    lines = [
        "【卖家精灵 MCP 工具规则 — 必须遵守】",
        "以下工具可以查询真实的 Amazon 市场数据（搜索量、竞价、供需比、竞品等）：",
    ]
    for name in mcp_names:
        lines.append(f"  - {name}")

    if "sellersprite_mcp_list_tools" in mcp_names:
        lines.append("")
        lines.append(
            "工作流程：当你被要求分析关键词/产品/市场时，"
            "必须先用 sellersprite_mcp_list_tools 查看所有可用工具，"
            "再选择合适的工具用 sellersprite_mcp_call_tool 调用。"
        )

    lines.append("")
    lines.append(
        "重要：你对 Amazon 数据的分析必须基于工具返回的真实数据，"
        "绝对不能使用训练数据或记忆中的数据来编造数字。"
        "如果工具返回了数据，必须引用其中的具体数值。"
        "如果没有返回数据或调用失败，必须如实告知用户。"
    )
    return "\n".join(lines)


def _tool_output_to_text(output: Any) -> str:
    if isinstance(output, BaseMessage):
        output = output.content
    if isinstance(output, str):
        return output
    return json.dumps(output, ensure_ascii=False, default=str)


def format_sellersprite_raw_data(tool_name: str, output: Any) -> str:
    """格式化卖家精灵 MCP 原始返回，确保用户能直接核对来源数据。"""
    raw_text = _tool_output_to_text(output)
    return f"\n【卖家精灵 MCP 原始数据】\n工具：{tool_name}\n{raw_text}\n"


def is_sellersprite_raw_data_request(message: str) -> bool:
    text = message.lower()
    return "原始数据" in text or (
        "raw" in text and ("data" in text or "mcp" in text or "sellersprite" in text)
    )


class ChatState(TypedDict):
    """聊天状态"""
    messages: Annotated[Sequence[BaseMessage], lambda x, y: list(x) + list(y)]


def create_chat_tools(chat_tools: ChatTools):
    """将 ChatTools 方法转换为 LangChain tool 装饰器"""

    @tool
    def query_sku_list(keyword: str = "") -> str:
        """查询SKU列表。可按关键词过滤（SKU、ASIN、店铺名称）。"""
        return chat_tools.query_sku_list(keyword if keyword else None)

    @tool
    def query_sales(sku: str = "", days: int = 7) -> str:
        """查询销售数据。参数: sku(可选), days(默认7天)。返回销量、销售额、排名等。"""
        return chat_tools.query_sales(sku if sku else None, days)

    @tool
    def query_ads(sku: str = "", days: int = 7) -> str:
        """查询广告数据。参数: sku(可选), days(默认7天)。返回ACOS、花费、点击等。"""
        return chat_tools.query_ads(sku if sku else None, days)

    @tool
    def query_inventory(sku: str = "") -> str:
        """查询库存数据。参数: sku(可选)。返回可售、在途、预留库存。"""
        return chat_tools.query_inventory(sku if sku else None)

    @tool
    def query_alerts(status: str = "", days: int = 7) -> str:
        """查询告警任务。参数: status(pending/processing/done/reviewed/ignored可选), days(默认7天)。"""
        return chat_tools.query_alerts(status if status else None, days)

    @tool
    def query_profit(sku: str = "", days: int = 30) -> str:
        """查询利润数据。参数: sku(可选), days(默认30天)。返回利润率、成本结构等。"""
        return chat_tools.query_profit(sku if sku else None, days)

    @tool
    def query_returns(sku: str = "", days: int = 30) -> str:
        """查询退货数据。参数: sku(可选), days(默认30天)。返回退货率、退货原因等。"""
        return chat_tools.query_returns(sku if sku else None, days)

    return [query_sku_list, query_sales, query_ads, query_inventory, query_alerts, query_profit, query_returns]


class ChatGraph:
    """聊天图"""

    def __init__(
        self,
        llm_client,
        chat_tools: ChatTools,
        *,
        mcp_tools_loader: Callable[[], Awaitable[list[Any]]] | None = None,
        memory_service=None,
    ):
        self.llm_client = llm_client
        self.chat_tools = chat_tools
        self.tools = create_chat_tools(chat_tools)
        self.mcp_tools_loader = mcp_tools_loader
        self.memory_service = memory_service
        self.mcp_tools_loaded = False
        self.mcp_load_error = ""
        self.local_tool_count = len(self.tools)
        self._last_sellersprite_raw_by_conversation: dict[str, str] = {}
        self.memory = MemorySaver()
        self.graph = self._build_graph()

    async def ensure_mcp_tools_loaded(self) -> None:
        """懒加载 MCP 工具，并合并到当前 LangGraph 工具池。"""
        if self.mcp_tools_loaded or self.mcp_tools_loader is None:
            return

        self.mcp_tools_loaded = True
        try:
            mcp_tools = await self.mcp_tools_loader()
        except Exception as exc:
            self.mcp_load_error = str(exc)
            return

        if not mcp_tools:
            return

        self.tools = [*self.tools, *mcp_tools]
        self.graph = self._build_graph()

    async def get_mcp_status(self) -> dict[str, Any]:
        """返回 MCP 工具加载状态，供总调度回答 MCP 调试类问题。"""
        await self.ensure_mcp_tools_loaded()
        mcp_tools = self.tools[self.local_tool_count:]
        return {
            "enabled": self.mcp_tools_loader is not None,
            "loaded": self.mcp_tools_loaded,
            "local_tool_count": self.local_tool_count,
            "mcp_tool_count": len(mcp_tools),
            "mcp_tool_names": [_tool_name(tool_item) for tool_item in mcp_tools],
            "load_error": self.mcp_load_error,
        }

    def _build_graph(self) -> StateGraph:
        """构建聊天图"""
        try:
            from langchain_openai import ChatOpenAI
        except ModuleNotFoundError:
            return None

        # 创建 LangChain LLM
        if hasattr(self.llm_client, 'api_key'):
            # DeepSeek LLM
            llm = ChatOpenAI(
                api_key=self.llm_client.api_key,
                base_url=self.llm_client.base_url,
                model=self.llm_client.model,
                temperature=0.3,
                streaming=True,
            )
        else:
            # 未接入 LangChain 聊天模型时不构建工具图。
            return None

        # 绑定工具
        llm_with_tools = llm.bind_tools(self.tools)

        # 创建工具节点
        tool_node = ToolNode(self.tools)

        def agent_node(state: ChatState) -> ChatState:
            """LLM 推理节点 — 动态注入 MCP 上下文到系统提示。"""
            messages = state["messages"]
            # 构建带 MCP 上下文的系统提示
            mcp_context = _build_mcp_system_addon(self.tools, self.local_tool_count)
            prompt = CHAT_SYSTEM_PROMPT + "\n\n" + mcp_context if mcp_context else CHAT_SYSTEM_PROMPT
            full_messages = [SystemMessage(content=prompt)] + list(messages)
            response = llm_with_tools.invoke(full_messages)
            return {"messages": [response]}

        def should_continue(state: ChatState) -> str:
            """路由：如果有工具调用，执行工具；否则结束"""
            last_message = state["messages"][-1]
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tools"
            return END

        # 构建图
        graph = StateGraph(ChatState)
        graph.add_node("agent", agent_node)
        graph.add_node("tools", tool_node)
        graph.set_entry_point("agent")
        graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
        graph.add_edge("tools", "agent")

        return graph.compile(checkpointer=self.memory)

    async def chat(self, message: str, conversation_id: str = "default") -> str:
        """发送消息并获取回复（非流式）"""
        await self.ensure_mcp_tools_loaded()
        self._record_user_message(conversation_id, message)
        prompted_message = self._build_prompted_message(conversation_id, message)
        if self.graph is None:
            response = self.llm_client.generate(CHAT_SYSTEM_PROMPT, prompted_message)
            self._record_assistant_message(conversation_id, response)
            return response

        config = {"configurable": {"thread_id": conversation_id}}
        input_state = {"messages": [HumanMessage(content=prompted_message)]}

        result = await self.graph.ainvoke(input_state, config=config)
        last_message = result["messages"][-1]
        self._record_assistant_message(conversation_id, last_message.content)
        return last_message.content

    async def chat_stream(self, message: str, conversation_id: str = "default"):
        """发送消息并获取流式回复"""
        await self.ensure_mcp_tools_loaded()
        self._record_user_message(conversation_id, message)
        if self.mcp_load_error:
            yield {"type": "error", "content": f"MCP 工具加载失败: {self.mcp_load_error}"}

        if is_sellersprite_raw_data_request(message):
            raw_data = self._get_sellersprite_raw(conversation_id)
            if raw_data:
                yield {"type": "token", "content": raw_data}
                yield {"type": "done", "conversation_id": conversation_id}
                self._record_assistant_message(conversation_id, raw_data)
                return

        prompted_message = self._build_prompted_message(conversation_id, message)
        assistant_chunks: list[str] = []
        if self.graph is None:
            try:
                response = self.llm_client.generate(CHAT_SYSTEM_PROMPT, prompted_message)
            except Exception as exc:
                yield {"type": "error", "content": str(exc)}
                yield {"type": "done", "conversation_id": conversation_id}
                return
            for char in response:
                assistant_chunks.append(char)
                yield {"type": "token", "content": char}
            yield {"type": "done", "conversation_id": conversation_id}
            self._record_assistant_message(conversation_id, "".join(assistant_chunks))
            return

        config = {"configurable": {"thread_id": conversation_id}}
        input_state = {"messages": [HumanMessage(content=prompted_message)]}

        # 实时流式状态
        has_tool_calls = False
        first_line_buffer = ""
        first_line_checked = False
        skip_first_line = False

        try:
            async for event in self.graph.astream_events(input_state, config=config, version="v2"):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if not content:
                        continue

                    if has_tool_calls:
                        # 工具调用后：实时流式输出（带第一行过滤）
                        if not first_line_checked:
                            first_line_buffer += content
                            if "\n" in first_line_buffer:
                                idx = first_line_buffer.index("\n")
                                first_line = first_line_buffer[:idx].strip()
                                if any(kw in first_line for kw in THINKING_KEYWORDS):
                                    skip_first_line = True
                                first_line_checked = True
                                remaining = first_line_buffer[idx + 1:]
                                if remaining and not skip_first_line:
                                    assistant_chunks.append(first_line_buffer[:idx + 1])
                                    yield {"type": "token", "content": first_line_buffer[:idx + 1]}
                                for char in remaining:
                                    assistant_chunks.append(char)
                                    yield {"type": "token", "content": char}
                        else:
                            assistant_chunks.append(content)
                            yield {"type": "token", "content": content}
                    else:
                        # 无工具调用：直接输出
                        assistant_chunks.append(content)
                        yield {"type": "token", "content": content}

                elif kind == "on_tool_start":
                    has_tool_calls = True
                    first_line_buffer = ""
                    first_line_checked = False
                    skip_first_line = False
                    yield {
                        "type": "tool_start",
                        "tool": event["name"],
                        "args": event["data"].get("input", {}),
                    }

                elif kind == "on_tool_end":
                    output = event["data"].get("output", "")
                    output_text = _tool_output_to_text(output)
                    result_preview = output_text[:3000]
                    yield {
                        "type": "tool_end",
                        "tool": event["name"],
                        "result": result_preview,
                    }
                    self._record_tool_message(
                        conversation_id,
                        tool_name=event["name"],
                        content=result_preview,
                        tool_result={"preview": result_preview},
                    )
                    mcp_tool_names = {
                        _tool_name(tool_item)
                        for tool_item in self.tools[self.local_tool_count:]
                    }
                    if event["name"] in mcp_tool_names or event["name"].startswith("sellersprite_"):
                        # 保存原始数据供后续查询（用户说"原始数据"时复用）
                        raw_data = format_sellersprite_raw_data(event["name"], output)
                        self._set_sellersprite_raw(conversation_id, raw_data)
                        assistant_chunks.append(raw_data)
                        yield {"type": "token", "content": raw_data}

        except Exception as e:
            yield {"type": "error", "content": str(e)}

        yield {"type": "done", "conversation_id": conversation_id}
        self._record_assistant_message(conversation_id, "".join(assistant_chunks))

    def _build_prompted_message(self, conversation_id: str, message: str) -> str:
        memory_context = ""
        if self.memory_service is not None:
            try:
                memory_context = self.memory_service.build_context(conversation_id)
            except Exception:
                memory_context = ""
        prompted_message = _build_memory_contextual_message(memory_context, message)
        return _build_contextual_message(self.tools, self.local_tool_count, prompted_message)

    def _record_user_message(self, conversation_id: str, message: str) -> None:
        if self.memory_service is None:
            return
        try:
            self.memory_service.record_user_message(conversation_id, message)
        except Exception:
            return

    def _record_assistant_message(self, conversation_id: str, message: str) -> None:
        if self.memory_service is None:
            return
        try:
            self.memory_service.record_assistant_message(conversation_id, message)
        except Exception:
            return

    def _record_tool_message(
        self,
        conversation_id: str,
        *,
        tool_name: str,
        content: str,
        tool_result: dict | None = None,
    ) -> None:
        if self.memory_service is None:
            return
        try:
            self.memory_service.record_tool_message(
                conversation_id,
                tool_name=tool_name,
                content=content,
                tool_result=tool_result,
            )
        except Exception:
            return

    def _set_sellersprite_raw(self, conversation_id: str, raw_data: str) -> None:
        if self.memory_service is not None:
            try:
                self.memory_service.set_sellersprite_raw(conversation_id, raw_data)
                return
            except Exception:
                pass
        self._last_sellersprite_raw_by_conversation[conversation_id] = raw_data

    def _get_sellersprite_raw(self, conversation_id: str) -> str | None:
        if self.memory_service is not None:
            try:
                raw_data = self.memory_service.get_sellersprite_raw(conversation_id)
                if raw_data:
                    return raw_data
            except Exception:
                pass
        return self._last_sellersprite_raw_by_conversation.get(conversation_id)
