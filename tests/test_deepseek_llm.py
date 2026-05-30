import os

import pytest

from app.agents.llm import DeepSeekLLMClient, StaticLLMClient, build_llm_client


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeHttpClient:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def post(self, url, json, headers, timeout):
        self.requests.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return self.response


def test_deepseek_client_posts_chat_completion_and_returns_content():
    http_client = FakeHttpClient(
        FakeResponse({"choices": [{"message": {"content": "检查广告搜索词和库存。"}}]})
    )
    client = DeepSeekLLMClient(
        api_key="sk-test",
        model="deepseek-chat",
        http_client=http_client,
    )

    result = client.generate("系统提示", "用户提示")

    assert result == "检查广告搜索词和库存。"
    request = http_client.requests[0]
    assert request["url"] == "https://api.deepseek.com/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer sk-test"
    assert request["json"]["model"] == "deepseek-chat"
    assert request["json"]["messages"] == [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": "用户提示"},
    ]
    assert request["json"]["temperature"] == 0.2


def test_deepseek_client_rejects_malformed_response():
    client = DeepSeekLLMClient(
        api_key="sk-test",
        http_client=FakeHttpClient(FakeResponse({"choices": []})),
    )

    with pytest.raises(RuntimeError, match="DeepSeek response missing content"):
        client.generate("系统提示", "用户提示")


def test_build_llm_client_uses_static_client_without_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    assert isinstance(build_llm_client(os.environ), StaticLLMClient)


def test_build_llm_client_uses_deepseek_when_configured(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")

    client = build_llm_client(os.environ)

    assert isinstance(client, DeepSeekLLMClient)
    assert client.model == "deepseek-reasoner"
