from app.agents.product_research_agent import ProductResearchAgent


class FakeMCPResearchService:
    def __init__(self, *, error=None):
        self.calls = []
        self.error = error

    async def research(self, *, keyword, marketplace, category):
        if self.error:
            raise self.error
        self.calls.append(
            {"keyword": keyword, "marketplace": marketplace, "category": category}
        )
        return {
            "keyword": keyword,
            "marketplace": marketplace,
            "category": category,
            "source_id": "trend-source",
            "source_name": "趋势数据",
            "raw_snapshot_ids": [17],
            "raw_data": {"keyword": keyword, "search_volume": 12000},
            "summary": "关键词 portable fan 搜索量 12000",
        }


def test_product_research_agent_uses_returned_source_name_and_snapshot_reference():
    import asyncio

    service = FakeMCPResearchService()
    agent = ProductResearchAgent(mcp_research_service=service)

    result = asyncio.run(
        agent.run(
            {
                "user_message": "这个关键词 portable fan 能不能做",
                "entities": {"keyword": "portable fan"},
            }
        )
    )

    assert result["agent_name"] == "ProductResearchAgent"
    assert result["keyword"] == "portable fan"
    assert result["raw"]["keyword"] == "portable fan"
    assert result["raw"]["source_id"] == "trend-source"
    assert result["raw"]["raw_data"]["search_volume"] == 12000
    assert "【数据来源：趋势数据】" in result["summary"]
    assert "原始快照：17" in result["summary"]
    assert "搜索量 12000" in result["summary"]
    assert service.calls == [
        {"keyword": "portable fan", "marketplace": "US", "category": "all"}
    ]
    assert "决策：" not in result["summary"]
    assert result["evidence"] == []
    assert result["actions"] == []


def test_product_research_agent_failure_has_no_actions_or_sensitive_error():
    import asyncio

    agent = ProductResearchAgent(
        mcp_research_service=FakeMCPResearchService(
            error=RuntimeError("Authorization Bearer secret-token")
        )
    )

    result = asyncio.run(agent.run({"entities": {"keyword": "portable fan"}}))

    assert result["actions"] == []
    assert result["evidence"] == []
    assert result["raw"] == {}
    assert "调用失败" in result["summary"]
    assert "secret-token" not in result["summary"]
