"""LangGraph 聊天 Agent - 支持多轮对话和工具调用"""
from __future__ import annotations

import json
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from app.agents.tools import ChatTools

# 系统提示词
CHAT_SYSTEM_PROMPT = """你是数据分析助手。

严格规则：
- 禁止使用 * 号
- 禁止使用 | 竖线
- 禁止使用 markdown 表格
- 禁止使用 emoji
- 禁止提问
- 每条数据占一行，一行内展示所有信息
- 重要内容用【】标注
- 数据和建议之间空一行

回复格式示例：
告警 1 SKU-001 可售天数低于补货周期 25 天 可售库存：40 在途：0 预留：0
告警 2 SKU-002 可售天数低于补货周期 22 天 可售库存：600 在途：100 预留：20
告警 3 SKU-003 可售天数低于补货周期 18 天 可售库存：100 在途：0 预留：0

【重点关注】SKU-001 和 SKU-003 在途库存为 0，建议尽快安排补货。
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

    def __init__(self, llm_client, chat_tools: ChatTools):
        self.llm_client = llm_client
        self.chat_tools = chat_tools
        self.tools = create_chat_tools(chat_tools)
        self.memory = MemorySaver()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """构建聊天图"""
        from langchain_openai import ChatOpenAI

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
            # 静态 LLM - 不支持工具调用，使用模拟响应
            return None

        # 绑定工具
        llm_with_tools = llm.bind_tools(self.tools)

        # 创建工具节点
        tool_node = ToolNode(self.tools)

        def agent_node(state: ChatState) -> ChatState:
            """LLM 推理节点"""
            messages = state["messages"]
            # 添加系统提示
            full_messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT)] + list(messages)
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
        if self.graph is None:
            # 静态 LLM 模式
            return self.llm_client.generate(CHAT_SYSTEM_PROMPT, message)

        config = {"configurable": {"thread_id": conversation_id}}
        input_state = {"messages": [HumanMessage(content=message)]}

        result = await self.graph.ainvoke(input_state, config=config)
        last_message = result["messages"][-1]
        return last_message.content

    async def chat_stream(self, message: str, conversation_id: str = "default"):
        """发送消息并获取流式回复"""
        if self.graph is None:
            # 静态 LLM 模式 - 模拟流式
            response = self.llm_client.generate(CHAT_SYSTEM_PROMPT, message)
            for char in response:
                yield {"type": "token", "content": char}
            yield {"type": "done", "conversation_id": conversation_id}
            return

        config = {"configurable": {"thread_id": conversation_id}}
        input_state = {"messages": [HumanMessage(content=message)]}

        # 实时流式状态
        has_tool_calls = False
        first_line_buffer = ""  # 缓冲第一行（判断是否是思考内容）
        first_line_checked = False
        skip_first_line = False
        line_buffer = ""

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
                                # 检查第一行是否是思考内容
                                if any(kw in first_line for kw in THINKING_KEYWORDS):
                                    skip_first_line = True
                                first_line_checked = True
                                # 输出第一行之后的内容
                                remaining = first_line_buffer[idx + 1:]
                                if remaining and not skip_first_line:
                                    yield {"type": "token", "content": first_line_buffer[:idx + 1]}
                                for char in remaining:
                                    yield {"type": "token", "content": char}
                        else:
                            # 第一行已检查，直接输出
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
                    if isinstance(output, str):
                        result_preview = output[:200]
                    else:
                        result_preview = str(output)[:200]
                    yield {
                        "type": "tool_end",
                        "tool": event["name"],
                        "result": result_preview,
                    }

        except Exception as e:
            yield {"type": "error", "content": str(e)}

        yield {"type": "done", "conversation_id": conversation_id}
