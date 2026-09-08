from __future__ import annotations

from collections.abc import Mapping

import httpx


class LLMClient:
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class StaticLLMClient(LLMClient):
    """测试替身：只在单元测试中显式注入，不作为生产兜底。"""

    def __init__(self, response: str = "建议检查关键指标并安排负责人处理。") -> None:
        self.response = response

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return self.response


class MissingLLMClient(LLMClient):
    """未配置真实 LLM 时拒绝生成，避免 Agent 返回固定分析。"""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise RuntimeError("未配置真实 LLM，无法生成 Agent 分析。请配置 DEEPSEEK_API_KEY。")


class DeepSeekLLMClient(LLMClient):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 30,
        http_client=None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self.http_client.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "stream": False,
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"DeepSeek response missing content: {payload}") from exc
        if not content:
            raise RuntimeError(f"DeepSeek response missing content: {payload}")
        return content


def build_llm_client(env: Mapping[str, str]) -> LLMClient:
    provider = env.get("LLM_PROVIDER", "static").lower()
    deepseek_key = env.get("DEEPSEEK_API_KEY", "")
    if provider == "deepseek" and deepseek_key:
        return DeepSeekLLMClient(
            api_key=deepseek_key,
            model=env.get("DEEPSEEK_MODEL", "deepseek-chat"),
            base_url=env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            timeout_seconds=float(env.get("DEEPSEEK_TIMEOUT_SECONDS", "30")),
        )
    return MissingLLMClient()
