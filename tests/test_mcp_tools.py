import asyncio

from app.agents.chat_graph import ChatGraph
from app.agents.chat_graph import format_sellersprite_raw_data
from app.agents.llm import MissingLLMClient, StaticLLMClient
from app.agents.mcp_tools import (
    build_sellersprite_mcp_config,
    create_sellersprite_generic_tools,
    load_sellersprite_mcp_tools,
)


class FakeMCPClient:
    instances = []

    def __init__(self, config):
        self.config = config
        FakeMCPClient.instances.append(self)

    async def get_tools(self):
        return ["seller-tool"]


class FakeChatTools:
    def query_sku_list(self, keyword=None):
        return "{}"

    def query_sales(self, sku=None, days=7):
        return "{}"

    def query_ads(self, sku=None, days=7):
        return "{}"

    def query_inventory(self, sku=None):
        return "{}"

    def query_alerts(self, status=None, days=7):
        return "{}"

    def query_profit(self, sku=None, days=30):
        return "{}"

    def query_returns(self, sku=None, days=30):
        return "{}"


class FakeNamedTool:
    name = "sellersprite_mcp_call_tool"


class FakeCompiledGraph:
    async def astream_events(self, input_state, config=None, version="v2"):
        yield {
            "event": "on_tool_end",
            "name": "sellersprite_mcp_call_tool",
            "data": {
                "output": '{"asin":"B0TEST0001","keyword":"portable fan","sales":1234}',
            },
        }


class FakeChunk:
    def __init__(self, content):
        self.content = content


class FakeFollowupCompiledGraph:
    async def astream_events(self, input_state, config=None, version="v2"):
        message = input_state["messages"][0].content
        if "原始数据" in message:
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": FakeChunk("我无法提供原始数据，因为您没有提供任何数据。")},
            }
            return
        yield {
            "event": "on_tool_end",
            "name": "sellersprite_mcp_call_tool",
            "data": {
                "output": '{"asin":"B0TEST0001","keyword":"portable fan","sales":1234}',
            },
        }


def test_sellersprite_mcp_config_is_disabled_without_url():
    assert build_sellersprite_mcp_config({}) is None


def test_sellersprite_mcp_config_builds_auth_headers():
    config = build_sellersprite_mcp_config(
        {
            "SELLERSPRITE_MCP_URL": "https://open.sellersprite.com/mcp",
            "SELLERSPRITE_API_KEY": "sk-seller",
            "SELLERSPRITE_MCP_TRANSPORT": "sse",
            "SELLERSPRITE_MCP_HEADERS": '{"X-Workspace": "amazon-agent"}',
        }
    )

    assert config == {
        "sellersprite": {
            "url": "https://open.sellersprite.com/mcp",
            "transport": "sse",
            "headers": {
                "Authorization": "Bearer sk-seller",
                "X-Workspace": "amazon-agent",
            },
        }
    }


def test_load_sellersprite_mcp_tools_uses_configured_client():
    FakeMCPClient.instances.clear()

    tools = asyncio.run(
        load_sellersprite_mcp_tools(
            {
                "SELLERSPRITE_MCP_URL": "https://open.sellersprite.com/mcp",
                "SELLERSPRITE_API_KEY": "sk-seller",
            },
            client_factory=FakeMCPClient,
        )
    )

    assert tools == ["seller-tool"]
    assert FakeMCPClient.instances[0].config["sellersprite"]["transport"] == "streamable_http"


def test_create_sellersprite_generic_tools_exposes_list_and_call_tools():
    config = build_sellersprite_mcp_config(
        {"SELLERSPRITE_MCP_URL": "https://mcp.sellersprite.com/mcp?secret-key=test"}
    )

    tools = create_sellersprite_generic_tools(config)

    assert [tool.name for tool in tools] == [
        "sellersprite_mcp_list_tools",
        "sellersprite_mcp_call_tool",
    ]


def test_chat_graph_can_merge_lazy_loaded_mcp_tools():
    async def load_tools():
        return ["seller-tool"]

    graph = ChatGraph(
        StaticLLMClient(),
        FakeChatTools(),
        mcp_tools_loader=load_tools,
    )

    asyncio.run(graph.ensure_mcp_tools_loaded())

    assert len(graph.tools) == 8
    assert graph.tools[-1] == "seller-tool"


def test_chat_graph_reports_mcp_status_after_loading_tools():
    async def load_tools():
        return ["seller-tool"]

    graph = ChatGraph(
        StaticLLMClient(),
        FakeChatTools(),
        mcp_tools_loader=load_tools,
    )

    status = asyncio.run(graph.get_mcp_status())

    assert status["enabled"] is True
    assert status["loaded"] is True
    assert status["local_tool_count"] == 7
    assert status["mcp_tool_count"] == 1
    assert status["mcp_tool_names"] == ["seller-tool"]


def test_format_sellersprite_raw_data_keeps_complete_tool_output():
    raw = '{"asin":"B0TEST0001","keyword":"portable fan","sales":1234}'

    text = format_sellersprite_raw_data("sellersprite_mcp_call_tool", raw)

    assert "【卖家精灵 MCP 原始数据】" in text
    assert "工具：sellersprite_mcp_call_tool" in text
    assert raw in text


def test_chat_stream_sends_complete_sellersprite_mcp_raw_data():
    graph = ChatGraph(
        StaticLLMClient(),
        FakeChatTools(),
    )
    graph.tools = [*graph.tools, FakeNamedTool()]
    graph.graph = FakeCompiledGraph()

    async def collect():
        events = []
        async for event in graph.chat_stream("查卖家精灵数据", "seller-raw"):
            events.append(event)
        return events

    events = asyncio.run(collect())
    raw_events = [
        event
        for event in events
        if event["type"] == "token" and "【卖家精灵 MCP 原始数据】" in event["content"]
    ]

    assert raw_events
    assert '"sales":1234' in raw_events[0]["content"]


def test_chat_stream_returns_previous_sellersprite_raw_data_on_followup():
    graph = ChatGraph(
        StaticLLMClient(),
        FakeChatTools(),
    )
    graph.tools = [*graph.tools, FakeNamedTool()]
    graph.graph = FakeFollowupCompiledGraph()

    async def collect(message):
        events = []
        async for event in graph.chat_stream(message, "seller-followup"):
            events.append(event)
        return events

    asyncio.run(collect("查卖家精灵数据"))
    events = asyncio.run(collect("原始数据呢"))
    text = "".join(event.get("content", "") for event in events if event["type"] == "token")

    assert "【卖家精灵 MCP 原始数据】" in text
    assert '"asin":"B0TEST0001"' in text
    assert '"sales":1234' in text


def test_chat_stream_reports_missing_llm_instead_of_fixed_response():
    graph = ChatGraph(
        MissingLLMClient(),
        FakeChatTools(),
    )

    async def collect():
        events = []
        async for event in graph.chat_stream("分析一下", "missing-llm"):
            events.append(event)
        return events

    events = asyncio.run(collect())

    assert events[0]["type"] == "error"
    assert "未配置真实 LLM" in events[0]["content"]
    assert all(event.get("content") != "建议检查关键指标并安排负责人处理。" for event in events)
