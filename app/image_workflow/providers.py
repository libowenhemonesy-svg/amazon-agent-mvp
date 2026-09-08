from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping

import httpx


DEFAULT_QWEN_MODEL = "qwen-image-2.0-pro"
DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"


@dataclass
class ImageProviderResult:
    images: list[bytes]
    mime_type: str = "image/png"
    metadata: dict[str, Any] = field(default_factory=dict)


class QwenImageProvider:
    name = "qwen"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_QWEN_BASE_URL,
        public_base_url: str = "",
        timeout_seconds: float = 120,
        http_client: Any = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.public_base_url = public_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "QwenImageProvider | None":
        env = os.environ if env is None else env
        api_key = (env.get("BAILIAN_API_KEY") or env.get("DASHSCOPE_API_KEY") or "").strip()
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            base_url=env.get("BAILIAN_IMAGE_BASE_URL", DEFAULT_QWEN_BASE_URL),
            public_base_url=env.get("PUBLIC_BASE_URL", ""),
            timeout_seconds=float(env.get("BAILIAN_IMAGE_TIMEOUT_SECONDS", "120")),
        )

    def generate(
        self,
        *,
        prompt: str,
        model: str = DEFAULT_QWEN_MODEL,
        size: str = "1024x1024",
        count: int = 1,
        image_urls: list[str] | None = None,
        negative_prompt: str = "",
    ) -> ImageProviderResult:
        content = [{"image": self._public_image_url(url)} for url in (image_urls or [])]
        content.append({"text": prompt})
        parameters: dict[str, Any] = {
            "n": count,
            "size": size.replace("x", "*").replace("X", "*"),
            "watermark": False,
            "prompt_extend": True,
        }
        if negative_prompt:
            parameters["negative_prompt"] = negative_prompt

        response = self.http_client.post(
            f"{self.base_url}/services/aigc/multimodal-generation/generation",
            json={
                "model": model,
                "input": {"messages": [{"role": "user", "content": content}]},
                "parameters": parameters,
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        urls = _extract_image_urls(payload)
        images = []
        for url in urls:
            image_response = self.http_client.get(url, timeout=self.timeout_seconds)
            image_response.raise_for_status()
            images.append(image_response.content)
        return ImageProviderResult(
            images=images,
            metadata={"provider": self.name, "model": model, "count": len(images)},
        )

    def _public_image_url(self, url: str) -> str:
        if url.startswith("data:image/"):
            return url
        if url.startswith(("https://", "http://")):
            return url
        if self.public_base_url and url.startswith("/"):
            return f"{self.public_base_url}{url}"
        raise RuntimeError("参考图片必须是公网地址或 Base64 图片数据")


def build_provider_registry(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = os.environ if env is None else env
    return {
        "qwen": QwenImageProvider.from_env(env),
        "openai": None,
        "google": None,
    }


def provider_statuses(env: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    env = os.environ if env is None else env
    qwen = QwenImageProvider.from_env(env)
    return [
        {
            "id": "qwen",
            "name": "阿里云百炼 / 千问图片",
            "configured": qwen is not None,
            "enabled": qwen is not None,
            "models": [DEFAULT_QWEN_MODEL, "qwen-image-2.0"],
        },
        {
            "id": "openai",
            "name": "OpenAI Image",
            "configured": bool((env.get("OPENAI_API_KEY") or "").strip()),
            "enabled": False,
            "models": [],
            "message": "提供商适配器已预留，当前版本未启用。",
        },
        {
            "id": "google",
            "name": "Google Image",
            "configured": bool((env.get("GOOGLE_API_KEY") or "").strip()),
            "enabled": False,
            "models": [],
            "message": "提供商适配器已预留，当前版本未启用。",
        },
    ]


def _extract_image_urls(payload: dict[str, Any]) -> list[str]:
    try:
        content = payload["output"]["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("千问图片接口未返回有效内容") from exc
    urls = [str(item["image"]) for item in content if isinstance(item, dict) and item.get("image")]
    if not urls:
        raise RuntimeError("千问图片接口未返回图片地址")
    return urls
