import asyncio

from app.agents.chat_graph import ChatGraph


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


class RecordingLLM:
    def __init__(self, response="已按记忆分析"):
        self.response = response
        self.user_prompts = []

    def generate(self, system_prompt, user_prompt):
        self.user_prompts.append(user_prompt)
        return self.response


class RecordingMemory:
    def __init__(self):
        self.user_messages = []
        self.assistant_messages = []
        self.raw_data = {}

    def build_context(self, conversation_id):
        return "【长期记忆】\n- 默认看美国站"

    def record_user_message(self, conversation_id, content):
        self.user_messages.append((conversation_id, content))

    def record_assistant_message(self, conversation_id, content):
        self.assistant_messages.append((conversation_id, content))

    def get_sellersprite_raw(self, conversation_id):
        return self.raw_data.get(conversation_id)

    def set_sellersprite_raw(self, conversation_id, raw_data):
        self.raw_data[conversation_id] = raw_data


def test_chat_graph_injects_memory_context_and_records_messages():
    llm = RecordingLLM("分析完成")
    memory = RecordingMemory()
    graph = ChatGraph(llm, FakeChatTools(), memory_service=memory)

    async def collect():
        events = []
        async for event in graph.chat_stream("分析便携风扇", "conv-memory"):
            events.append(event)
        return events

    events = asyncio.run(collect())

    assert "【可参考记忆】" in llm.user_prompts[0]
    assert "默认看美国站" in llm.user_prompts[0]
    assert "用户消息：分析便携风扇" in llm.user_prompts[0]
    assert memory.user_messages == [("conv-memory", "分析便携风扇")]
    assert memory.assistant_messages == [("conv-memory", "分析完成")]
    assert events[-1] == {"type": "done", "conversation_id": "conv-memory"}
