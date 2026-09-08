from app.agents.product_listing_agent import ProductListingAgent


class RecordingLLM:
    def __init__(self):
        self.calls = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return (
            "Title: Portable Fan USB-C Rechargeable Quiet Desk Fan\n"
            "Bullet Points:\n"
            "- Quiet airflow for office use\n"
            "- USB-C rechargeable battery\n"
            "- Compact handheld design\n"
            "- Three adjustable speeds\n"
            "- Travel-ready cooling\n"
            "Description: Compact cooling for travel and desktop use.\n"
            "Search Terms: portable fan desk fan rechargeable fan"
        )


def test_product_listing_agent_generates_listing_from_research_context():
    llm = RecordingLLM()
    agent = ProductListingAgent(llm_client=llm)

    result = agent.run(
        {"entities": {}, "user_message": "根据刚才关键词生成Listing"},
        research_context={
            "keyword": "portable fan",
            "decision": {"label": "谨慎测试"},
            "competitors": [{"asin": "B0TEST0001"}],
        },
    )

    assert result["agent_name"] == "ProductListingAgent"
    assert result["keyword"] == "portable fan"
    assert result["listing"]["title"] == "Portable Fan USB-C Rechargeable Quiet Desk Fan"
    assert result["listing"]["bullet_points"][0] == "Quiet airflow for office use"
    assert result["listing"]["search_terms"] == "portable fan desk fan rechargeable fan"
    assert "ProductListingAgent" in llm.calls[0][0]
    assert "portable fan" in llm.calls[0][1]


def test_product_listing_agent_requires_keyword():
    agent = ProductListingAgent(llm_client=RecordingLLM())

    result = agent.run({"entities": {}, "user_message": "生成Listing"}, research_context={})

    assert "请先提供关键词" in result["summary"]
    assert result["listing"] == {}


def test_product_listing_agent_does_not_generate_fixed_listing_without_llm():
    agent = ProductListingAgent(llm_client=None)

    result = agent.run(
        {"entities": {"keyword": "portable fan"}, "user_message": "生成Listing"},
        research_context={},
    )

    assert "未配置真实 LLM" in result["summary"]
    assert result["listing"] == {}


def test_product_listing_agent_does_not_fallback_to_fixed_listing_for_bad_llm_output():
    class BadLLM:
        def generate(self, system_prompt: str, user_prompt: str) -> str:
            return "无法生成"

    agent = ProductListingAgent(llm_client=BadLLM())

    result = agent.run(
        {"entities": {"keyword": "portable fan"}, "user_message": "生成Listing"},
        research_context={},
    )

    assert "没有返回可解析的 Listing" in result["summary"]
    assert result["listing"] == {}


def test_product_listing_agent_parses_markdown_sections_and_numbered_bullets():
    class MarkdownLLM:
        def generate(self, system_prompt: str, user_prompt: str) -> str:
            return (
                "**Title:** Rechargeable Portable Fan for Travel\n\n"
                "**Bullet Points:**\n"
                "1. Three speed airflow for desk and travel use\n"
                "2. USB rechargeable battery for cordless convenience\n"
                "3. Quiet motor for work and bedroom use\n"
                "4. Compact handheld design for bags and commutes\n"
                "5. Easy controls for everyday cooling\n\n"
                "**Description:** A compact rechargeable fan for personal cooling.\n\n"
                "**Search Terms:** portable fan handheld fan rechargeable fan"
            )

    result = ProductListingAgent(llm_client=MarkdownLLM()).run(
        {"entities": {"keyword": "portable fan"}},
        research_context={},
    )

    assert result["listing"]["title"] == "Rechargeable Portable Fan for Travel"
    assert len(result["listing"]["bullet_points"]) == 5
    assert result["listing"]["search_terms"] == "portable fan handheld fan rechargeable fan"


def test_product_listing_agent_parses_json_listing_response():
    class JsonLLM:
        def generate(self, system_prompt: str, user_prompt: str) -> str:
            return (
                '{"title":"Rechargeable Portable Fan for Travel",'
                '"bullet_points":["Three speeds","USB rechargeable","Quiet motor",'
                '"Handheld design","Easy controls"],'
                '"description":"A compact rechargeable fan for personal cooling.",'
                '"search_terms":"portable fan handheld fan rechargeable fan"}'
            )

    result = ProductListingAgent(llm_client=JsonLLM()).run(
        {"entities": {"keyword": "portable fan"}},
        research_context={},
    )

    assert result["listing"]["title"] == "Rechargeable Portable Fan for Travel"
    assert result["listing"]["bullet_points"] == [
        "Three speeds",
        "USB rechargeable",
        "Quiet motor",
        "Handheld design",
        "Easy controls",
    ]
