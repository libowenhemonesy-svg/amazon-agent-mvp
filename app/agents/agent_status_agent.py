from __future__ import annotations

from typing import Any


AGENT_REGISTRY = [
    {
        "name": "OrchestratorAgent",
        "display_name": "总调度 Agent",
        "role": "理解用户意图、选择合适专业 Agent 或工具、管理任务状态并汇总结果。",
    },
    {
        "name": "ProductResearchAgent",
        "display_name": "选品研究 Agent",
        "role": "分析关键词搜索量、竞品、市场容量、价格带、竞争强度，并判断产品是否值得做。",
    },
    {
        "name": "ProductImageAgent",
        "display_name": "产品图生成 Agent",
        "role": "根据 Listing 卖点和选品关键词生成产品图提示词，并在配置阿里百炼后生成主图或场景图。",
    },
    {
        "name": "ProductListingAgent",
        "display_name": "Listing 文案生成 Agent",
        "role": "根据选品研究上下文生成 Amazon 标题、五点描述、长描述和后台搜索词。",
    },
    {
        "name": "ChatGraph",
        "display_name": "通用工具执行图",
        "role": "执行 SKU、销量、库存、利润、退货、告警和 MCP 工具查询。",
    },
]


class AgentStatusAgent:
    """用当前大模型基于真实 Agent 注册表回答系统能力问题。"""

    def __init__(self, *, llm_client) -> None:
        self.llm_client = llm_client

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        user_message = state.get("user_message", "")
        answer = self.llm_client.generate(
            _system_prompt(),
            _user_prompt(user_message),
        ).strip()
        return {
            "agent_name": "AgentStatusAgent",
            "summary": answer,
            "agents": AGENT_REGISTRY,
        }


def _system_prompt() -> str:
    return (
        "你是 Amazon Agent 项目的总调度 Agent。"
        "用户询问当前系统有哪些 Agent、能做什么、如何分工时，"
        "必须只基于提供的 Agent 注册表回答。"
        "用自然中文回答，简洁准确，不要声称系统只有一个 AI 助手。"
    )


def _user_prompt(user_message: str) -> str:
    lines = [
        f"用户问题：{user_message}",
        "",
        "当前 Agent 注册表：",
    ]
    for index, agent in enumerate(AGENT_REGISTRY, start=1):
        lines.append(
            f"{index}. {agent['name']} / {agent['display_name']}：{agent['role']}"
        )
    return "\n".join(lines)
