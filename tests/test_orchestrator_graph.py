import asyncio

from app.agents.orchestrator_graph import OrchestratorGraph, classify_intent, extract_entities


class FakeChatGraph:
    def __init__(self):
        self.calls = []

    async def chat_stream(self, message: str, conversation_id: str = "default"):
        self.calls.append((message, conversation_id))
        yield {"type": "token", "content": "本地数据查询结果"}
        yield {"type": "done", "conversation_id": conversation_id}

    async def get_mcp_status(self):
        return {
            "enabled": True,
            "loaded": True,
            "local_tool_count": 7,
            "mcp_tool_count": 2,
            "mcp_tool_names": ["sellersprite_mcp_list_tools", "sellersprite_mcp_call_tool"],
            "load_error": "",
        }


def collect_stream(graph, message: str, conversation_id: str = "default"):
    async def run():
        events = []
        async for event in graph.chat_stream(message, conversation_id):
            events.append(event)
        return events

    return asyncio.run(run())


def test_classify_intent_routes_common_business_requests():
    assert classify_intent("查一下 SKU-001 最近7天销量") == "data_query"
    assert classify_intent("这个关键词 portable fan 能不能做") == "product_research"
    assert classify_intent("根据刚才关键词生成产品图") == "image_generation"
    assert classify_intent("测试图片生成功能") == "image_generation"
    assert classify_intent("根据刚才关键词生成Listing") == "listing_generation"
    assert classify_intent("你有几个agent") == "agent_status"
    assert classify_intent("测试mcp") == "mcp_status"
    assert classify_intent("SKU-001 ACOS 太高怎么优化") == "ads_optimization"
    assert classify_intent("SKU-001 库存还能撑多久") == "inventory_check"
    assert classify_intent("生成今天运营日报") == "report_generation"


def test_extract_entities_reads_sku_asin_keyword_and_days():
    entities = extract_entities("帮我分析 SKU-001 最近14天，关键词 portable fan，ASIN B0ABC12345")

    assert entities["sku"] == "SKU-001"
    assert entities["asin"] == "B0ABC12345"
    assert entities["keyword"] == "portable fan"
    assert entities["days"] == 14


def test_orchestrator_falls_back_to_chat_graph_for_data_query():
    chat_graph = FakeChatGraph()
    graph = OrchestratorGraph(chat_graph=chat_graph)

    events = collect_stream(graph, "查一下 SKU-001 最近7天销量", "conv-1")

    assert chat_graph.calls == [("查一下 SKU-001 最近7天销量", "conv-1")]
    assert events[-1] == {"type": "done", "conversation_id": "conv-1"}
    assert graph.last_state["intent"] == "data_query"
    assert graph.last_state["route"] == "chat_graph"
    assert graph.last_state["task_status"] == "completed"


def test_orchestrator_routes_product_research_to_specialized_executor():
    async def product_research_executor(state):
        return {
            "summary": f"关键词 {state['entities']['keyword']} 建议谨慎测试",
            "evidence": ["样本竞品 10 个"],
            "actions": ["继续采集竞品", "验证 CPC"],
        }

    graph = OrchestratorGraph(
        chat_graph=FakeChatGraph(),
        executors={"product_research": product_research_executor},
    )

    events = collect_stream(graph, "这个关键词 portable fan 能不能做", "conv-2")
    text = "".join(event.get("content", "") for event in events if event["type"] == "token")

    assert "本地数据查询结果" in text
    assert graph.last_state["intent"] == "product_research"
    # product_research 改为直走 chat_graph，由 AI 调用 MCP 获取真实数据
    assert graph.last_state["route"] == "chat_graph"
    assert graph.last_state["task_status"] == "completed"


def test_orchestrator_stores_product_research_context_for_image_generation():
    """product_research 改为直走 chat_graph，不再经过 executor。"""
    async def product_image_executor(state):
        return {
            "agent_name": "ProductImageAgent",
            "summary": "已生成产品图",
            "image_url": "/static/generated/test.png",
            "prompt": "photo of portable fan",
            "keyword": "portable fan",
        }

    graph = OrchestratorGraph(
        chat_graph=FakeChatGraph(),
        executors={
            "product_image": product_image_executor,
        },
    )

    # 第一次：产品研究请求走 chat_graph
    events1 = collect_stream(graph, "这个关键词 portable fan 能不能做", "conv-image")
    text1 = "".join(event.get("content", "") for event in events1 if event["type"] == "token")
    assert "本地数据查询结果" in text1
    assert graph.last_state["intent"] == "product_research"
    assert graph.last_state["route"] == "chat_graph"

    # 第二次：图片生成仍然走 executor
    events2 = collect_stream(graph, "根据刚才关键词生成产品图", "conv-image")
    text2 = "".join(event.get("content", "") for event in events2 if event["type"] == "token")
    assert any(event["type"] == "image" and event["url"] == "/static/generated/test.png" for event in events2)
    assert "图片链接：/static/generated/test.png" in text2
    assert graph.last_state["intent"] == "image_generation"
    assert graph.last_state["route"] == "product_image"


def test_orchestrator_runs_listing_after_research_and_passes_listing_to_image_generation():
    """product_research 改为直走 chat_graph，listing 和 image 仍然走 executor。"""

    async def product_listing_executor(state):
        return {
            "agent_name": "ProductListingAgent",
            "keyword": state["entities"].get("keyword", ""),
            "summary": "已生成 Listing",
            "listing": {
                "title": "Portable Fan USB-C Rechargeable Quiet Desk Fan",
                "bullet_points": ["Quiet airflow for office use", "USB-C rechargeable battery"],
                "description": "Compact cooling for travel and desktop use.",
                "search_terms": "portable fan desk fan rechargeable fan",
            },
        }

    async def product_image_executor(state):
        return {
            "agent_name": "ProductImageAgent",
            "summary": "已生成产品图",
            "image_url": "/static/generated/listing-image.png",
            "prompt": "photo of portable fan",
            "keyword": state["entities"].get("keyword", ""),
        }

    graph = OrchestratorGraph(
        chat_graph=FakeChatGraph(),
        executors={
            "product_listing": product_listing_executor,
            "product_image": product_image_executor,
        },
    )

    # 第一步：产品研究请求 → chat_graph（不再是 executor）
    events1 = collect_stream(graph, "这个关键词 portable fan 能不能做", "conv-listing")
    text1 = "".join(event.get("content", "") for event in events1 if event["type"] == "token")
    assert "本地数据查询结果" in text1
    assert graph.last_state["intent"] == "product_research"
    assert graph.last_state["route"] == "chat_graph"

    # 第二步：Listing 生成 → executor（带关键词）
    events2 = collect_stream(graph, "关键词：portable fan 生成Listing", "conv-listing")
    text2 = "".join(event.get("content", "") for event in events2 if event["type"] == "token")
    assert "已生成 Listing" in text2
    assert graph.last_state["intent"] == "listing_generation"

    # 第三步：图片生成 → executor（带关键词）
    events3 = collect_stream(graph, "关键词：portable fan 生成产品图", "conv-listing")
    assert any(event["type"] == "image" and event["url"] == "/static/generated/listing-image.png" for event in events3)
    assert graph.last_state["intent"] == "image_generation"


def test_orchestrator_reports_missing_keyword_for_image_generation_without_context():
    graph = OrchestratorGraph(chat_graph=FakeChatGraph(), executors={"product_image": lambda state: {}})

    events = collect_stream(graph, "生成产品图", "empty-context")
    text = "".join(event.get("content", "") for event in events if event["type"] == "token")

    assert "请先提供关键词" in text


def test_orchestrator_answers_agent_status_without_falling_back_to_chat_graph():
    chat_graph = FakeChatGraph()

    def agent_status_executor(state):
        return {
            "agent_name": "AgentStatusAgent",
            "summary": "大模型自然回答：当前有 ProductResearchAgent 和 ProductImageAgent。",
        }

    graph = OrchestratorGraph(
        chat_graph=chat_graph,
        executors={"agent_status": agent_status_executor},
    )

    events = collect_stream(graph, "你有几个agent", "agent-status")
    text = "".join(event.get("content", "") for event in events if event["type"] == "token")

    assert chat_graph.calls == []
    assert "大模型自然回答" in text
    assert "ProductResearchAgent" in text
    assert "ProductImageAgent" in text
    assert graph.last_state["intent"] == "agent_status"


def test_orchestrator_answers_mcp_status_without_falling_back_to_chat_graph():
    chat_graph = FakeChatGraph()
    graph = OrchestratorGraph(chat_graph=chat_graph)

    events = collect_stream(graph, "测试mcp", "mcp-status")
    text = "".join(event.get("content", "") for event in events if event["type"] == "token")

    # MCP 状态查询通过 chat_graph 让 AI 自然回复
    assert len(chat_graph.calls) == 1
    # 传给 AI 的上下文包含 MCP 状态数据
    assert "sellersprite_mcp_list_tools" in chat_graph.calls[0][0]
    assert graph.last_state["intent"] == "mcp_status"
