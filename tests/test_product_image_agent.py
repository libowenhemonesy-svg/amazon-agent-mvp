import base64
import os

from app.agents.product_image_agent import BailianImageClient, DoubaoArkImageClient, ProductImageAgent


class FakeArkClient:
    def __init__(self, image_bytes: bytes):
        self.image_bytes = image_bytes
        self.calls = []

    def generate_image(self, prompt: str) -> bytes:
        self.calls.append(prompt)
        return self.image_bytes


class FakeHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def post(self, url, json, headers, timeout):
        self.requests.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse(self.payload)

    def get(self, url, timeout):
        self.requests.append({"url": url, "timeout": timeout})
        return FakeBinaryResponse(b"downloaded-png")


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeBinaryResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


def test_product_image_agent_generates_prompt_without_api_key(tmp_path):
    agent = ProductImageAgent(output_dir=tmp_path, ark_client=None)

    result = agent.run(
        {
            "entities": {"keyword": "portable fan"},
            "user_message": "根据关键词生成产品图",
        },
        research_context={"keyword": "portable fan"},
    )

    assert result["agent_name"] == "ProductImageAgent"
    assert result["keyword"] == "portable fan"
    assert result["image_url"] == ""
    assert "portable fan" in result["prompt"]
    assert "BAILIAN_API_KEY" in result["summary"]
    assert "千问" in result["summary"]


def test_doubao_ark_image_client_requires_api_key_and_model():
    assert DoubaoArkImageClient.from_env({"ARK_API_KEY": "ark-key"}) is None
    assert DoubaoArkImageClient.from_env({"ARK_IMAGE_MODEL": "seedream-model"}) is None

    client = DoubaoArkImageClient.from_env(
        {
            "ARK_API_KEY": "ark-key",
            "ARK_IMAGE_MODEL": "seedream-model",
        }
    )

    assert client is not None
    assert client.api_key == "ark-key"
    assert client.model == "seedream-model"


def test_bailian_image_client_uses_qwen_image_defaults():
    client = BailianImageClient.from_env({"BAILIAN_API_KEY": "bailian-key"})

    assert client is not None
    assert client.api_key == "bailian-key"
    assert client.model == "qwen-image-2.0-pro"
    assert client.base_url == "https://dashscope.aliyuncs.com/api/v1"


def test_bailian_image_client_accepts_dashscope_api_key_alias():
    client = BailianImageClient.from_env({"DASHSCOPE_API_KEY": "dashscope-key"})

    assert client is not None
    assert client.api_key == "dashscope-key"


def test_product_image_agent_saves_mock_image_and_returns_url(tmp_path):
    agent = ProductImageAgent(output_dir=tmp_path, ark_client=FakeArkClient(b"png-bytes"))

    result = agent.run(
        {"entities": {"keyword": "portable fan"}, "user_message": "生成主图"},
        research_context={"keyword": "portable fan"},
    )

    assert result["image_url"].startswith("/static/generated/")
    saved_name = os.path.basename(result["image_url"])
    assert (tmp_path / saved_name).read_bytes() == b"png-bytes"
    assert result["image_type"] == "main_image"


def test_product_image_agent_uses_listing_benefits_in_prompt(tmp_path):
    fake_client = FakeArkClient(b"png-bytes")
    agent = ProductImageAgent(output_dir=tmp_path, ark_client=fake_client)

    agent.run(
        {"entities": {"keyword": "portable fan"}, "user_message": "生成场景图"},
        research_context={
            "keyword": "portable fan",
            "listing": {
                "title": "Portable Fan USB-C Rechargeable Quiet Desk Fan",
                "bullet_points": ["Quiet airflow for office use", "USB-C rechargeable battery"],
            },
        },
    )

    prompt = fake_client.calls[0]
    assert "Portable Fan USB-C Rechargeable Quiet Desk Fan" in prompt
    assert "Quiet airflow for office use" in prompt
    assert "USB-C rechargeable battery" in prompt


def test_doubao_ark_image_client_posts_to_images_generation_api():
    image_payload = base64.b64encode(b"png-bytes").decode()
    http_client = FakeHttpClient({"data": [{"b64_json": image_payload}]})
    client = DoubaoArkImageClient(
        api_key="ark-key",
        model="ark-model",
        base_url="https://ark.example.test/api/v3",
        size="1024x1024",
        http_client=http_client,
    )

    image = client.generate_image("commercial product photo")

    assert image == b"png-bytes"
    request = http_client.requests[0]
    assert request["url"] == "https://ark.example.test/api/v3/images/generations"
    assert request["headers"]["Authorization"] == "Bearer ark-key"
    assert request["json"]["model"] == "ark-model"
    assert request["json"]["prompt"] == "commercial product photo"
    assert request["json"]["size"] == "1024x1024"


def test_bailian_image_client_posts_to_openai_compatible_images_api():
    http_client = FakeHttpClient(
        {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"image": "https://dashscope-result.example.test/image.png"},
                            ],
                        },
                    },
                ],
            },
        }
    )
    client = BailianImageClient(
        api_key="bailian-key",
        model="qwen-image-2.0-pro",
        base_url="https://dashscope.example.test/api/v1",
        size="1024x1024",
        http_client=http_client,
    )

    image = client.generate_image("commercial product photo")

    assert image == b"downloaded-png"
    request = http_client.requests[0]
    assert request["url"] == "https://dashscope.example.test/api/v1/services/aigc/multimodal-generation/generation"
    assert request["headers"]["Authorization"] == "Bearer bailian-key"
    assert request["json"]["model"] == "qwen-image-2.0-pro"
    assert request["json"]["input"]["messages"][0]["content"][0]["text"] == "commercial product photo"
    assert request["json"]["parameters"]["size"] == "1024*1024"
    assert request["json"]["parameters"]["watermark"] is False
