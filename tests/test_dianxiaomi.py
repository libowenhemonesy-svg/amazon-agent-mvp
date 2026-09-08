from fastapi.testclient import TestClient

from app.integrations.dianxiaomi.attributes import generate_dianxiaomi_attributes
from app.agents.llm import MissingLLMClient
from app.main import create_app
from app.routes.dianxiaomi import init_dianxiaomi_agent


class RecordingLLM:
    def __init__(self, response: str):
        self.calls = []
        self.response = response

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.response


class SequencedLLM:
    def __init__(self, responses: list[str]):
        self.calls = []
        self.responses = list(responses)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.responses.pop(0)


def test_generate_dianxiaomi_attributes_uses_listing_and_returns_required_fields():
    llm = RecordingLLM(
        """
        ```json
        {
          "title": "Portable Fan USB Rechargeable Quiet Desk Fan",
          "product_identifier": "Portable Fan Black",
          "product_id_type": "EAN",
          "brand": "CoolBreeze",
          "manufacturer": "CoolBreeze",
          "sales_form": "single",
          "color": "Black",
          "description": "Compact cooling for travel and desk use.",
          "bullet_points": ["Quiet airflow", "USB rechargeable", "Compact size"],
          "standard_price": 19.99,
          "quantity": 100,
          "condition_type": "new_new",
          "product_type": "HOME",
          "item_keywords": "portable-fan",
          "search_terms": "portable fan usb rechargeable quiet",
          "shipping_channel": "FBM"
        }
        ```
        """
    )

    result = generate_dianxiaomi_attributes(
        llm_client=llm,
        listing={
            "title": "Portable Fan USB Rechargeable Quiet Desk Fan",
            "bullets": ["Quiet airflow", "USB rechargeable", "Compact size"],
            "description": "Compact cooling for travel and desk use.",
            "search_terms": "portable fan usb rechargeable quiet",
        },
        product_context="brand CoolBreeze, price 19.99, black",
        marketplace="US",
    )

    assert result["title"] == "Portable Fan USB Rechargeable Quiet Desk Fan"
    assert result["brand"] == "CoolBreeze"
    assert len(result["bullet_points"]) == 5
    assert result["shipping_channel"] == "FBM"
    assert "Portable Fan USB Rechargeable Quiet Desk Fan" in llm.calls[0][1]
    assert "不要重写 Listing" in llm.calls[0][0]


def test_dianxiaomi_generate_endpoint_rejects_missing_llm():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    init_dianxiaomi_agent(llm_client=MissingLLMClient())
    client = TestClient(app)

    response = client.post(
        "/api/dianxiaomi/generate-attributes",
        json={
            "keyword": "portable fan",
            "product_context": "brand CoolBreeze",
            "marketplace": "US",
        },
    )

    assert response.status_code == 503
    assert "未配置真实 LLM" in response.json()["detail"]


def test_dianxiaomi_generate_endpoint_returns_listing_and_attributes():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    init_dianxiaomi_agent(
        llm_client=SequencedLLM(
            [
                (
                    "Title: Portable Fan USB Rechargeable Quiet Desk Fan\n"
                    "Bullet Points:\n"
                    "- Quiet airflow\n"
                    "- USB rechargeable\n"
                    "- Compact size\n"
                    "- Three speeds\n"
                    "- Travel ready\n"
                    "Description: Compact cooling for travel and desk use.\n"
                    "Search Terms: portable fan usb rechargeable quiet"
                ),
                """
                {"brand":"CoolBreeze","manufacturer":"CoolBreeze","product_identifier":"Portable Fan Black",
                "color":"Black","standard_price":19.99,"product_type":"HOME","item_keywords":"portable-fan"}
                """,
            ]
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/dianxiaomi/generate-attributes",
        json={
            "keyword": "portable fan",
            "product_context": "brand CoolBreeze, price 19.99, black",
            "marketplace": "US",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["listing"]["title"] == "Portable Fan USB Rechargeable Quiet Desk Fan"
    assert payload["attributes"]["brand"] == "CoolBreeze"
    assert len(payload["attributes"]["bullet_points"]) == 5


def test_dianxiaomi_generate_endpoint_rejects_missing_keyword_or_context():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post(
        "/api/dianxiaomi/generate-attributes",
        json={"keyword": " ", "product_context": "Portable fan"},
    )
    assert response.status_code == 400

    response = client.post(
        "/api/dianxiaomi/generate-attributes",
        json={"keyword": "portable fan", "product_context": " "},
    )
    assert response.status_code == 400


def test_dianxiaomi_fill_rejects_empty_attributes_and_continue_writes_signal():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    response = client.post("/api/dianxiaomi/fill", json={"attributes": {}})
    assert response.status_code == 400

    response = client.post("/api/dianxiaomi/fill/continue", json={"step": "category"})
    assert response.status_code == 200
    assert response.json()["signal"] == "category"

    response = client.get("/api/dianxiaomi/fill/status")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_frontend_contains_dianxiaomi_fill_entry():
    app = create_app(database_url="sqlite+pysqlite:///:memory:", feishu_enabled=False)
    client = TestClient(app)

    html = client.get("/").text
    js = client.get("/static/app.js").text

    assert "生成并填写店小秘" in html
    assert "runDianxiaomiFill" in js
    assert "/api/dianxiaomi/generate-attributes" in js
