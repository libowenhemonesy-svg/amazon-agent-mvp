from app.agents.agent_status_agent import AgentStatusAgent


class RecordingLLM:
    def __init__(self):
        self.calls = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return "你现在有 2 个专业 agent：选品研究 Agent 和产品图生成 Agent。"


def test_agent_status_agent_uses_llm_with_agent_registry():
    llm = RecordingLLM()
    agent = AgentStatusAgent(llm_client=llm)

    result = agent.run({"user_message": "你有几个agent"})

    assert result["agent_name"] == "AgentStatusAgent"
    assert result["summary"] == "你现在有 2 个专业 agent：选品研究 Agent 和产品图生成 Agent。"
    assert llm.calls
    system_prompt, user_prompt = llm.calls[0]
    assert "总调度 Agent" in system_prompt
    assert "ProductResearchAgent" in user_prompt
    assert "ProductImageAgent" in user_prompt
    assert "ChatGraph" in user_prompt
